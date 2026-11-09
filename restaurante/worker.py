import os
import sys
import json
import django
import pika
import redis
import uuid
from decouple import config

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from django.db import connection, IntegrityError, transaction
from collections import Counter
from restaurante.models import (
    ComandaRecibida, Comensal, Factura, PedidoCabecera, PedidoDetalle, PedidoDetalleCompartido, PedidoDetalleExtra, PedidoDetalleModificador,
    Producto, RecetaExtra,
)
from restaurante.comensales_calculos import RETIRADO, estado_inicial_de_comanda, mensaje_comensal_retirado
from restaurante.especiales import precios_especiales, precio_a_cobrar, precio_segun_lo_que_vio
from restaurante.recetas import consumir_pedido, mensaje_para_cliente, motivo_para_personal
from restaurante.stock import StockInsuficiente
from restaurante.stock_calculos import clave_de_linea, precio_de_renglon

r = redis.Redis(host=config('REDIS_HOST', default='127.0.0.1'), port=config('REDIS_PORT', default=6379, cast=int), decode_responses=True)


def insertar_comanda_control(uuid_str, id_pedido_cabecera):
    """Insercion directa por SQL, evitando la conversion problematica
    de pyodbc al enviar UUID como parametro. El string ya fue validado
    con uuid.UUID(...) antes de llegar aca, asi que es seguro embeberlo."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO ComandaRecibida (IdComandaUuid, IdPedidoCabecera, FechaHoraRecepcion) "
            f"OUTPUT INSERTED.Id "
            f"VALUES ('{uuid_str}', %s, %s)",
            [id_pedido_cabecera, timezone.now()]
        )
        return cursor.fetchone()[0]  # Id de la comanda, para ligarle sus items


MENSAJE_GENERICO = 'Insumos insuficientes. Disculpe las molestias.'
MENSAJE_CUENTA_EN_CURSO = 'La cuenta de la mesa ya esta en curso: no se pueden enviar mas pedidos. Avisa al mozo.'


def marcar_rechazada(id_comanda, motivo, mensaje):
    """La comanda queda registrada como rechazada (sin items y sin descontar nada): si RabbitMQ reentrega el mensaje
    se reconoce por su UUID y no se procesa de nuevo. El motivo es solo para el personal; el cliente ve el mensaje."""
    ComandaRecibida.objects.filter(pk=id_comanda).update(estado='Rechazada', motivo=motivo[:500], mensaje_cliente=mensaje[:300])


def procesar_comanda(ch, method, properties, body):
    datos = json.loads(body)

    try:
        uuid_valido = uuid.UUID(datos['id_comanda_uuid'])  # valida el formato, lanza ValueError si esta mal
    except (ValueError, KeyError):
        print(f"[ERROR] Payload con UUID invalido, se descarta: {body}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    uuid_str = str(uuid_valido)  # forma canonica, segura para embeber en SQL
    rechazo = None  # (motivo, mensaje) si la comanda no se pudo preparar por falta de stock

    try:
        with transaction.atomic():
            # la fila de la sesion se bloquea: emitir la factura bloquea la misma fila, asi una comanda y la factura de la
            # misma mesa se ordenan (o entra la comanda y la factura la incluye, o la factura sale y la comanda se rechaza)
            pedido_cabecera = PedidoCabecera.objects.select_for_update().get(id=datos['id_pedido_cabecera'])

            id_comanda = insertar_comanda_control(uuid_str, pedido_cabecera.id)

            # especiales de la jornada en que se abrio la mesa (sin jornada: precio normal)
            precios_esp = {}
            if pedido_cabecera.jornada_id is not None:
                jornada = pedido_cabecera.jornada
                precios_esp = precios_especiales(jornada.fecha, jornada.turno_id)

            # el cliente paga el precio que vio (si cambio despues) salvo que ahora sea menor; ver precio_segun_lo_que_vio
            # (hito 5) cada item puede traer 'sin': los ids de los insumos que el cliente pidio quitar. Dos unidades del
            # mismo plato van al mismo renglon solo si piden lo mismo; los mensajes anteriores a esto no traen 'sin'.
            # 'compartido' (hito 3): nombres entre quienes se divide el plato; mismas unidades con distinto reparto = otro renglon
            # 'extras' (cobros, hito 5): [{'id', 'cantidad', 'precio' (el que el cliente vio)}]; mismos extras = mismo renglon
            conteo = Counter(
                (item['id'], item.get('precio'), tuple(sorted(set(item.get('sin') or []))),
                 tuple(sorted({str(n).strip() for n in (item.get('compartido') or []) if str(n).strip()}, key=str.casefold)),
                 tuple(sorted((e['id'], e['cantidad'], e.get('precio')) for e in (item.get('extras') or []))))
                for item in datos['items']
            )
            unidades = Counter(
                clave_de_linea(item['id'], item.get('sin'), [(e['id'], e['cantidad']) for e in (item.get('extras') or [])])
                for item in datos['items']
            )

            comensal = (datos.get('comensal') or '').strip()[:50] or None

            # el perfil del comensal (mesa grupal): se vuelve a verificar con la sesion bloqueada, por si se retiro mientras la
            # comanda esperaba en la cola
            comensal_obj = None
            if datos.get('id_comensal'):
                comensal_obj = Comensal.objects.filter(pk=datos['id_comensal'], pedido_cabecera=pedido_cabecera).first()
                if comensal_obj is not None:
                    comensal = comensal_obj.nombre
                    ComandaRecibida.objects.filter(pk=id_comanda).update(comensal_id=comensal_obj.id)

            if pedido_cabecera.estado != 'Abierto':
                rechazo = ('La sesion de la mesa ya esta cerrada.', 'La mesa ya no esta abierta. Avisa al mozo.')
            elif Factura.objects.filter(pedido_cabecera=pedido_cabecera, estado__in=('Emitida', 'Pagada')).exists():
                rechazo = ('La mesa tiene la cuenta en curso (factura emitida): no recibe pedidos.', MENSAJE_CUENTA_EN_CURSO)
            elif datos.get('id_comensal') and (comensal_obj is None or comensal_obj.estado == RETIRADO):
                rechazo = ('El comensal ya no esta en la mesa (se retiro).', mensaje_comensal_retirado())

            # Primero el stock, todo o nada: descuenta los insumos de las recetas por FEFO. Si el ultimo stock lo
            # tomo otra comanda antes, esta se rechaza y no queda nada a medias (el punto de guardado la deshace).
            if rechazo is None:
                try:
                    with transaction.atomic():
                        faltantes = consumir_pedido(dict(unidades), id_comanda, pedido_cabecera.jornada_id)
                        if faltantes:
                            rechazo = (motivo_para_personal(faltantes), mensaje_para_cliente(faltantes))
                        else:
                            for (id_producto, precio_visto, sin, compartido, extras), cantidad in conteo.items():
                                producto = Producto.objects.get(id=id_producto)
                                precio = precio_segun_lo_que_vio(precio_a_cobrar(producto, precios_esp), precio_visto)
                                # cada extra se cobra al precio que el cliente vio (o menos, si bajo); el renglon = plato + recargos
                                filas_extra = []
                                for id_extra, unidades_extra, visto_extra in extras:
                                    extra = RecetaExtra.objects.get(id=id_extra)
                                    filas_extra.append((extra, unidades_extra, precio_segun_lo_que_vio(extra.precio, visto_extra)))
                                precio = precio_de_renglon(precio, [(p, n) for _, n, p in filas_extra])
                                detalle = PedidoDetalle.objects.create(
                                    pedido_cabecera=pedido_cabecera,
                                    comanda_id=id_comanda,
                                    producto=producto,
                                    cantidad=cantidad,
                                    precio_unitario=precio,
                                    sub_total=precio * cantidad,
                                    identificador_comensal=comensal,
                                    estado_cocina=False
                                )
                                if sin:  # lo quitado no se descuenta (ya lo resolvio consumir_pedido); aca solo se registra
                                    PedidoDetalleModificador.objects.bulk_create(
                                        [PedidoDetalleModificador(detalle=detalle, insumo_id=id_insumo) for id_insumo in sin]
                                    )
                                if filas_extra:  # el stock de los extras ya lo descontó consumir_pedido; aca solo se registran
                                    PedidoDetalleExtra.objects.bulk_create([
                                        PedidoDetalleExtra(detalle=detalle, extra=extra, insumo_id=extra.insumo_id, cantidad=n, precio_unitario=p)
                                        for extra, n, p in filas_extra
                                    ])
                                if compartido:  # plato dividido: el total del renglon se reparte entre estos participantes
                                    PedidoDetalleCompartido.objects.bulk_create(
                                        [PedidoDetalleCompartido(detalle=detalle, participante=nombre) for nombre in compartido]
                                    )
                except RecetaExtra.DoesNotExist:
                    # un extra borrado a mano de la base: no se acepta la comanda (nada se descontó, el punto de guardado lo deshace)
                    rechazo = ('Un extra pedido ya no existe.', 'Un extra del pedido ya no esta disponible. Actualiza el menu y volve a pedir.')
                except StockInsuficiente as error:
                    # no deberia pasar (los lotes estaban bloqueados), pero si pasa se rechaza igual
                    rechazo = (f'Stock insuficiente de {error.insumo.nombre}.', MENSAJE_GENERICO)

            if rechazo is not None:
                marcar_rechazada(id_comanda, *rechazo)
            else:
                # dentro de la transaccion: asi nunca hay una comanda aceptada sin estado en Redis (una comanda sin estado se
                # toma por entregada y no bloquearia el cobro). Si el commit fallara, la clave queda sola y es inofensiva.
                # una mesa grupal, antes de la primera ronda, deja la comanda 'retenida': descuenta stock pero la cocina no la ve
                # hasta que todos dan el OK (o el mozo la libera). La sesion esta bloqueada, asi que no se cruza con la liberacion.
                r.set(f'comanda:estado:{uuid_str}', estado_inicial_de_comanda(pedido_cabecera.modalidad, pedido_cabecera.ronda_liberada))

        if rechazo is not None:
            print(f'[RECHAZADA] Comanda {uuid_str}: {rechazo[0]}')
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        print(f'[OK] Comanda {uuid_str} procesada.')

    except IntegrityError:
        print(f'[DUPLICADO] Comanda {uuid_str} ya estaba procesada, se ignora.')

    except Producto.DoesNotExist:
        print(f'[ERROR] Comanda {uuid_str}: producto inexistente, se descarta.')

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    parametros = pika.ConnectionParameters(
        host=config('RABBIT_HOST', default='localhost'),
        credentials=pika.PlainCredentials(
            config('RABBIT_USER'), config('RABBIT_PASS')
        )
    )
    conexion = pika.BlockingConnection(parametros)
    canal = conexion.channel()
    canal.queue_declare(queue='comandas_pendientes', durable=True)
    canal.basic_qos(prefetch_count=1)
    canal.basic_consume(queue='comandas_pendientes', on_message_callback=procesar_comanda)

    print('Worker escuchando comandas_pendientes. Ctrl+C para salir.')
    canal.start_consuming()


if __name__ == '__main__':
    main()