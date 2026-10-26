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
from restaurante.models import ComandaRecibida, PedidoCabecera, PedidoDetalle, Producto
from restaurante.especiales import precios_especiales, precio_a_cobrar, precio_segun_lo_que_vio
from restaurante.recetas import consumir_pedido, mensaje_para_cliente, motivo_para_personal
from restaurante.stock import StockInsuficiente

r = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)


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
            pedido_cabecera = PedidoCabecera.objects.get(id=datos['id_pedido_cabecera'])

            id_comanda = insertar_comanda_control(uuid_str, pedido_cabecera.id)

            # especiales de la jornada en que se abrio la mesa (sin jornada: precio normal)
            precios_esp = {}
            if pedido_cabecera.jornada_id is not None:
                jornada = pedido_cabecera.jornada
                precios_esp = precios_especiales(jornada.fecha, jornada.turno_id)

            # el cliente paga el precio que vio (si cambio despues) salvo que ahora sea menor; ver precio_segun_lo_que_vio
            conteo = Counter((item['id'], item.get('precio')) for item in datos['items'])
            unidades = Counter(item['id'] for item in datos['items'])

            # Primero el stock, todo o nada: descuenta los insumos de las recetas por FEFO. Si el ultimo stock lo
            # tomo otra comanda antes, esta se rechaza y no queda nada a medias (el punto de guardado la deshace).
            try:
                with transaction.atomic():
                    faltantes = consumir_pedido(dict(unidades), id_comanda, pedido_cabecera.jornada_id)
                    if faltantes:
                        rechazo = (motivo_para_personal(faltantes), mensaje_para_cliente(faltantes))
                    else:
                        for (id_producto, precio_visto), cantidad in conteo.items():
                            producto = Producto.objects.get(id=id_producto)
                            precio = precio_segun_lo_que_vio(precio_a_cobrar(producto, precios_esp), precio_visto)
                            PedidoDetalle.objects.create(
                                pedido_cabecera=pedido_cabecera,
                                comanda_id=id_comanda,
                                producto=producto,
                                cantidad=cantidad,
                                precio_unitario=precio,
                                sub_total=precio * cantidad,
                                estado_cocina=False
                            )
            except StockInsuficiente as error:
                # no deberia pasar (los lotes estaban bloqueados), pero si pasa se rechaza igual
                rechazo = (f'Stock insuficiente de {error.insumo.nombre}.', MENSAJE_GENERICO)

            if rechazo is not None:
                marcar_rechazada(id_comanda, *rechazo)

        if rechazo is not None:
            print(f'[RECHAZADA] Comanda {uuid_str}: {rechazo[0]}')
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        r.set(f'comanda:estado:{uuid_str}', 'pendiente')
        print(f'[OK] Comanda {uuid_str} procesada.')

    except IntegrityError:
        print(f'[DUPLICADO] Comanda {uuid_str} ya estaba procesada, se ignora.')

    except Producto.DoesNotExist:
        print(f'[ERROR] Comanda {uuid_str}: producto inexistente, se descarta.')

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    parametros = pika.ConnectionParameters(
        host='localhost',
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