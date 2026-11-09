"""Cuenta de una mesa: emitir la factura, cobrar en efectivo, anular y cerrar la mesa.

Reglas (hito 3):
- La factura (cuenta interna) se emite al empezar a cobrar y necesita la caja ABIERTA. Congela el total, los renglones y
  cuanto equivale en USD, BRL y PYG. Hay una vigente por sesion. Mientras haya una factura vigente la mesa no recibe
  comandas nuevas (el worker las rechaza); para pedir algo mas el mozo cierra la sesion y abre otra.
- No se cobra mientras haya comandas en `pendiente` o `proceso` en cocina (`listo` no bloquea).
- Se puede pagar en partes y combinando medios. saldo = total - pagos aprobados - pagos pendientes.
- Efectivo: un pago, una moneda. El sistema convierte con la cotizacion vigente y la congela en el pago. El vuelto es siempre
  en pesos y lo calcula el sistema. La propina es opcional (en pesos), va solo al mozo de la mesa y queda en la caja como
  ingreso con concepto Propina.
- Cada cobro bloquea la fila de la factura y la de la caja dentro de una transaccion: no se cobra dos veces ni se pisa el
  saldo. Reintentar con la misma `clave` devuelve el mismo pago.
- Solo se anulan pagos en EFECTIVO (Admin/Gerente, con motivo): se registra el contramovimiento en la caja.
- Una mesa se cierra sin consumo o con la factura pagada. Con saldo, solo Admin/Gerente la fuerzan, con motivo. Con un pago
  pendiente no se cierra nunca.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .caja import ReglaCaja, caja_abierta, caja_abierta_bloqueada, cotizacion_para, registrar_movimiento
from .cobros_calculos import CERO, MONEDA_BASE, CobroInvalido, calcular_cobro_efectivo, calcular_cobro_tarjeta, convertir_a_ars
from .cobros_calculos import equivalentes
from .cotizacion import cotizaciones_vigentes
from .comensales_calculos import ESTADOS_ACTIVOS
from .cuenta_calculos import (
    SIN_ASIGNAR, desglose_por_comensal, descripcion_de_renglon, partes_de_ingreso, saldo_de_la_cuenta, total_aprobado,
)
from .extras import texto_extras
from .modificadores import nombres_quitados
from .models import (
    Factura, FacturaDetalle, MetodoPago, Pago, PagoEvento, PedidoCabecera, PedidoDetalle,
)
from .redis_client import redis_client

ESTADOS_QUE_BLOQUEAN_EL_COBRO = ('retenida', 'pendiente', 'proceso')   # retenida: la primera ronda de una mesa grupal todavia no salio
ESTADOS_FACTURA_VIGENTE = ('Emitida', 'Pagada')


class ReglaCuenta(Exception):
    """Una regla de la cuenta impide la operacion. Se responde 409 (o el `estado` que indique). Mensaje listo para mostrar."""

    def __init__(self, mensaje, estado=409, **extra):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.estado = estado
        self.extra = extra


# ---------- lecturas ----------

def factura_vigente(sesion):
    return Factura.objects.filter(pedido_cabecera=sesion, estado__in=ESTADOS_FACTURA_VIGENTE).order_by('-id').first()


def comandas_en_cocina(sesion):
    """UUID de las comandas de la sesion que todavia estan `pendiente` o en `proceso` (bloquean el cobro).
    El estado vive en Redis; una comanda que ya no esta ahi fue entregada. Las rechazadas no cuentan."""
    en_cocina = []
    for comanda in sesion.comandas.filter(estado='Aceptada'):
        estado = redis_client.get(f'comanda:estado:{comanda.id_comanda_uuid}')
        if estado in ESTADOS_QUE_BLOQUEAN_EL_COBRO:
            en_cocina.append(str(comanda.id_comanda_uuid))
    return en_cocina


def comandas_sin_entregar(sesion):
    """UUID de las comandas aceptadas de la sesion que todavia no se entregaron (retenida, pendiente, proceso o listo): con alguna
    de ellas la mesa no se puede cerrar. Una comanda entregada o cancelada ya no tiene estado en Redis."""
    activas = []
    for comanda in sesion.comandas.filter(estado='Aceptada'):
        if redis_client.get(f'comanda:estado:{comanda.id_comanda_uuid}') in ESTADOS_ACTIVOS:
            activas.append(str(comanda.id_comanda_uuid))
    return activas


def detalles_de_sesion(sesion):
    return list(sesion.detalles.select_related('producto').prefetch_related(
        'compartido', 'modificadores__insumo', 'extras__insumo').order_by('id'))


def total_de_sesion(sesion):
    return sesion.detalles.aggregate(t=Sum('sub_total'))['t'] or CERO


def _pagos_como_dicts(factura):
    return [{'estado': p.estado, 'monto': p.monto} for p in Pago.objects.filter(factura=factura)]


def saldo_de_factura(factura):
    return saldo_de_la_cuenta(factura.total, _pagos_como_dicts(factura))


def _metodo(nombre):
    metodo = MetodoPago.objects.filter(nombre=nombre).first()
    if metodo is None:
        raise ReglaCuenta(f"Falta el metodo de pago '{nombre}'. Ejecutar sql/19_AE4_Cuenta_Pagos_Migraciones.sql.", estado=500)
    return metodo


def _evento(pago, evento, anterior, nuevo, empleado, detalle=None):
    PagoEvento.objects.create(
        pago=pago, fecha_hora=timezone.now(), evento=evento, estado_anterior=anterior, estado_nuevo=nuevo,
        detalle=(detalle or '')[:400] or None, empleado=empleado,
    )


def _bloquear_sesion(sesion_id):
    # sin select_related: en SQL Server el bloqueo con joins puede tomar candados de mas tablas (mesa, empleado)
    return PedidoCabecera.objects.select_for_update().get(pk=sesion_id)


# ---------- emitir la factura ----------

def emitir_factura(sesion_id, empleado):
    """Emite la factura de la sesion (o devuelve la vigente). Devuelve (factura, creada)."""
    with transaction.atomic():
        sesion = _bloquear_sesion(sesion_id)
        if sesion.estado != 'Abierto':
            raise ReglaCuenta('La sesion ya esta cerrada.')
        existente = factura_vigente(sesion)
        if existente is not None:
            return existente, False
        if caja_abierta() is None:
            raise ReglaCuenta('No hay una caja abierta. Un Admin o Gerente debe abrirla antes de cobrar.')
        detalles = detalles_de_sesion(sesion)
        total = sum((d.sub_total for d in detalles), CERO)
        if total <= 0:
            raise ReglaCuenta('La mesa no tiene consumo para cobrar. Si se van sin pedir, cerrar la sesion.')

        cot = cotizaciones_vigentes()
        eq = equivalentes(total, cot)
        factura = Factura.objects.create(
            pedido_cabecera=sesion, fecha_hora_emision=timezone.now(), total=total, estado='Emitida',
            total_usd=eq['USD'], total_brl=eq['BRL'], total_pyg=eq['PYG'],
            cotizacion_usd=cot.get('USD'), cotizacion_brl=cot.get('BRL'), cotizacion_pyg=cot.get('PYG'),
            empleado=empleado,
        )
        FacturaDetalle.objects.bulk_create([
            FacturaDetalle(
                factura=factura, pedido_detalle=d, producto=d.producto,
                descripcion=descripcion_de_renglon(d.producto.nombre, nombres_quitados(d), texto_extras(d)),
                cantidad=d.cantidad, precio_unitario=d.precio_unitario, sub_total=d.sub_total,
                identificador_comensal=d.identificador_comensal,
            ) for d in detalles
        ])
    return factura, True


# ---------- cobro en efectivo ----------

def pagar_efectivo(factura_id, empleado, moneda, recibido, propina_ars=CERO, monto_cuenta=None, clave=None):
    """Cobra en efectivo (una moneda). `recibido` esta en `moneda`; `propina_ars` y `monto_cuenta` en pesos.
    Devuelve (pago, creado). `creado=False` si la `clave` ya existia (reintento). Levanta ReglaCuenta/ReglaCaja (409) o
    CobroInvalido (400)."""
    with transaction.atomic():
        factura = Factura.objects.select_for_update().get(pk=factura_id)   # sin select_related (ver _bloquear_sesion)
        if clave:
            previo = Pago.objects.filter(clave_idempotencia=clave).first()
            if previo is not None:
                if previo.factura_id != factura.id:
                    raise ReglaCuenta('Esa clave de operacion ya se uso en otra cuenta.')
                return previo, False
        if factura.estado == 'Anulada':
            raise ReglaCuenta('La factura esta anulada.')
        sesion = factura.pedido_cabecera
        if sesion.estado != 'Abierto':
            raise ReglaCuenta('La mesa ya se cerro.')
        caja = caja_abierta_bloqueada()
        if caja is None:
            raise ReglaCuenta('No hay una caja abierta. Un Admin o Gerente debe abrirla antes de cobrar.')
        en_cocina = comandas_en_cocina(sesion)
        if en_cocina:
            raise ReglaCuenta(
                'Todavia hay pedidos en preparacion: se cobra cuando la mesa tenga todo lo pedido.',
                comandas_en_cocina=en_cocina,
            )

        saldo = saldo_de_la_cuenta(factura.total, _pagos_como_dicts(factura))
        cot = cotizacion_para(moneda)
        recibido_ars = recibido if moneda == MONEDA_BASE else convertir_a_ars(recibido, cot)
        cobro = calcular_cobro_efectivo(recibido_ars, saldo, propina_ars, monto_cuenta)

        pago = Pago.objects.create(
            factura=factura, metodo_pago=_metodo('Efectivo'), monto=cobro['aplicado'], fecha_hora=timezone.now(),
            estado='Aprobado', moneda=moneda, monto_recibido=recibido, cotizacion=cot,
            monto_propina=cobro['propina'], vuelto=cobro['vuelto'], empleado=empleado,
            empleado_propina=sesion.empleado if cobro['propina'] > 0 else None,
            clave_idempotencia=clave or None,
        )
        _evento(pago, 'Cobrado en efectivo', None, 'Aprobado', empleado,
                f"Recibido {recibido} {moneda}; cuenta {cobro['aplicado']}, propina {cobro['propina']}, vuelto {cobro['vuelto']} (ARS).")

        venta, propina = partes_de_ingreso(recibido, cobro['propina'], cot, moneda)
        if venta > 0:
            registrar_movimiento(caja, 'Ingreso', 'Venta', moneda, venta, empleado, pago=pago,
                                 descripcion=f'Cobro de la cuenta de la mesa {sesion.mesa.numero}')
        if propina > 0:
            registrar_movimiento(caja, 'Ingreso', 'Propina', moneda, propina, empleado, pago=pago,
                                 descripcion=f'Propina de la mesa {sesion.mesa.numero}')
        if cobro['vuelto'] > 0:
            registrar_movimiento(caja, 'Egreso', 'Vuelto', MONEDA_BASE, cobro['vuelto'], empleado, pago=pago,
                                 descripcion=f'Vuelto de la mesa {sesion.mesa.numero}')

        _actualizar_factura(factura, vuelto_extra=cobro['vuelto'])
    return pago, True


def pagar_tarjeta(factura_id, empleado, monto_cuenta=None, clave=None):
    """Registra un cobro con tarjeta (credito o debito) CONFIRMADO por el mozo: el pago es manual, con el postnet; aca solo se
    asienta que la plata impacto. Es en pesos, sin vuelto ni propina y no mueve el efectivo de la caja (pero, como todo cobro,
    pide una caja abierta). `monto_cuenta` (pesos): cuanto de la cuenta cubre; sin indicar, todo el saldo.
    Devuelve (pago, creado). `creado=False` si la `clave` ya existia (reintento). Levanta ReglaCuenta (409) o CobroInvalido (400)."""
    with transaction.atomic():
        factura = Factura.objects.select_for_update().get(pk=factura_id)   # sin select_related (ver _bloquear_sesion)
        if clave:
            previo = Pago.objects.filter(clave_idempotencia=clave).first()
            if previo is not None:
                if previo.factura_id != factura.id:
                    raise ReglaCuenta('Esa clave de operacion ya se uso en otra cuenta.')
                return previo, False
        if factura.estado == 'Anulada':
            raise ReglaCuenta('La factura esta anulada.')
        sesion = factura.pedido_cabecera
        if sesion.estado != 'Abierto':
            raise ReglaCuenta('La mesa ya se cerro.')
        if caja_abierta() is None:
            raise ReglaCuenta('No hay una caja abierta. Un Admin o Gerente debe abrirla antes de cobrar.')
        en_cocina = comandas_en_cocina(sesion)
        if en_cocina:
            raise ReglaCuenta(
                'Todavia hay pedidos en preparacion: se cobra cuando la mesa tenga todo lo pedido.',
                comandas_en_cocina=en_cocina,
            )
        # un pago pendiente (Mercado Pago) ya reserva su monto en el saldo: se puede combinar con la tarjeta
        monto = calcular_cobro_tarjeta(saldo_de_la_cuenta(factura.total, _pagos_como_dicts(factura)), monto_cuenta)
        pago = Pago.objects.create(
            factura=factura, metodo_pago=_metodo('Tarjeta'), monto=monto, fecha_hora=timezone.now(), estado='Aprobado',
            moneda=MONEDA_BASE, monto_recibido=monto, cotizacion=1, monto_propina=CERO, vuelto=CERO, empleado=empleado,
            clave_idempotencia=clave or None,
        )
        _evento(pago, 'Cobrado con tarjeta', None, 'Aprobado', empleado,
                f'El mozo confirmo el cobro con tarjeta de la mesa {sesion.mesa.numero}: {monto} (ARS).')
        _actualizar_factura(factura)
    return pago, True


def _actualizar_factura(factura, vuelto_extra=CERO):
    """Despues de cualquier cambio de pagos: marca Pagada cuando lo aprobado cubre el total, o vuelve a Emitida."""
    pagos = _pagos_como_dicts(factura)
    cubierta = total_aprobado(pagos) >= factura.total
    cambios = {}
    if cubierta and factura.estado == 'Emitida':
        cambios.update(estado='Pagada', fecha_hora_pago=timezone.now())
    elif not cubierta and factura.estado == 'Pagada':
        cambios.update(estado='Emitida', fecha_hora_pago=None)
    if vuelto_extra:
        cambios['cambio_entregado'] = (factura.cambio_entregado or CERO) + vuelto_extra
    if cambios:
        Factura.objects.filter(pk=factura.pk).update(**cambios)
        for campo, valor in cambios.items():
            setattr(factura, campo, valor)
        if 'estado' in cambios:
            _sincronizar_comprobante(factura)


def _sincronizar_comprobante(factura):
    """Hito 6: si la factura quedo Pagada (o dejo de estarlo) se guarda o borra su comprobante en Facturas/. Se importa aca porque
    comprobante.py usa este modulo."""
    from .comprobante import sincronizar_en_facturas
    sincronizar_en_facturas(factura.pk)


# ---------- anulaciones ----------

def anular_pago(pago_id, empleado, motivo):
    """Anula un pago aprobado en EFECTIVO o con TARJETA (Admin/Gerente). En efectivo hace el contramovimiento en la caja abierta;
    la tarjeta no movio la caja, asi que solo se anula el pago (sirve para corregir un cobro confirmado por error)."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise ReglaCuenta('Indicar el motivo de la anulacion.', estado=400)
    with transaction.atomic():
        pago = Pago.objects.select_related('metodo_pago', 'factura').get(pk=pago_id)
        factura = Factura.objects.select_for_update().get(pk=pago.factura_id)
        pago = Pago.objects.select_related('metodo_pago').get(pk=pago_id)   # estado actualizado, ya con la factura bloqueada
        if pago.metodo_pago.nombre not in ('Efectivo', 'Tarjeta'):
            raise ReglaCuenta('Solo se pueden anular pagos en efectivo o con tarjeta.')
        en_efectivo = pago.metodo_pago.nombre == 'Efectivo'
        if pago.estado != 'Aprobado':
            raise ReglaCuenta(f'El pago esta en estado {pago.estado}: solo se anula uno Aprobado.')
        if factura.pedido_cabecera.estado != 'Abierto':
            raise ReglaCuenta('La mesa ya se cerro: no se puede anular el pago.')
        mesa = factura.pedido_cabecera.mesa.numero
        if en_efectivo:
            caja = caja_abierta_bloqueada()
            if caja is None:
                raise ReglaCuenta('No hay una caja abierta para registrar la devolucion.')
            # se devuelve todo lo recibido (en su moneda) y se recupera el vuelto que se habia dado en pesos
            registrar_movimiento(caja, 'Egreso', 'Anulacion', pago.moneda, pago.monto_recibido, empleado, pago=pago,
                                 controlar_saldo=False, descripcion=f'Anulacion del pago {pago.id} (mesa {mesa}): {motivo}'[:200])
            if pago.vuelto > 0:
                registrar_movimiento(caja, 'Ingreso', 'Anulacion', MONEDA_BASE, pago.vuelto, empleado, pago=pago,
                                     descripcion=f'Vuelto devuelto por la anulacion del pago {pago.id} (mesa {mesa})'[:200])
        Pago.objects.filter(pk=pago.pk).update(
            estado='Anulado', fecha_hora_anulacion=timezone.now(), empleado_anulacion=empleado, motivo_anulacion=motivo[:200])
        _evento(pago, 'Anulado', 'Aprobado', 'Anulado', empleado, motivo)
        factura.cambio_entregado = (factura.cambio_entregado or CERO) - pago.vuelto
        Factura.objects.filter(pk=factura.pk).update(cambio_entregado=factura.cambio_entregado)
        _actualizar_factura(factura)
    return Pago.objects.get(pk=pago_id)


def anular_factura(factura_id, empleado, motivo):
    """Anula una factura sin pagos aprobados ni pendientes (Admin/Gerente). La mesa vuelve a poder pedir."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise ReglaCuenta('Indicar el motivo de la anulacion.', estado=400)
    with transaction.atomic():
        factura = Factura.objects.select_for_update().get(pk=factura_id)
        if factura.estado == 'Anulada':
            raise ReglaCuenta('La factura ya esta anulada.')
        if factura.pedido_cabecera.estado != 'Abierto':
            raise ReglaCuenta('La mesa ya se cerro.')
        con_pagos = Pago.objects.filter(factura=factura, estado__in=('Aprobado', 'Pendiente')).exists()
        if con_pagos:
            raise ReglaCuenta('La factura tiene pagos aprobados o pendientes: anular o resolver primero esos pagos.')
        Factura.objects.filter(pk=factura.pk).update(
            estado='Anulada', fecha_hora_anulacion=timezone.now(), empleado_anulacion=empleado, motivo_anulacion=motivo[:200])
    return Factura.objects.get(pk=factura_id)


# ---------- cierre de mesa ----------

def cerrar_sesion(sesion_id, empleado, es_admin_o_gerente, forzar=False, motivo=None):
    """Cierra la sesion y libera la mesa. Sin consumo o con la factura pagada: siempre. Con saldo: 409, salvo que Admin o
    Gerente fuercen con motivo. Con un pago pendiente: 409 siempre (hay un cobro sin resolver)."""
    motivo = (motivo or '').strip()
    with transaction.atomic():
        sesion = _bloquear_sesion(sesion_id)
        if sesion.estado != 'Abierto':
            raise ReglaCuenta('La sesion ya esta cerrada.')
        factura = factura_vigente(sesion)
        if factura is not None and Pago.objects.filter(factura=factura, estado='Pendiente').exists():
            raise ReglaCuenta('Hay un pago pendiente de resolver: esperar a que se apruebe o se cancele antes de cerrar la mesa.')

        # una comanda sin entregar (incluida la retenida de la primera ronda) no se abandona: se entrega o se cancela antes.
        # Solo un Admin o Gerente puede forzar el cierre (con motivo): lo que no empezo a prepararse se cancela con devolucion de
        # stock y lo que ya estaba en preparacion se da por entregado.
        sin_entregar = comandas_sin_entregar(sesion)
        if sin_entregar:
            if not forzar:
                raise ReglaCuenta(
                    'La mesa tiene pedidos sin entregar. Esperar a que se entreguen o cancelarlos (POST /pedidos/{uuid}/cancelar) '
                    'antes de cerrar la mesa.',
                    codigo='comandas_pendientes', comandas_pendientes=sin_entregar)
            if not es_admin_o_gerente:
                raise ReglaCuenta('Solo un Admin o Gerente puede cerrar una mesa con pedidos sin entregar.', estado=403,
                                  codigo='comandas_pendientes', comandas_pendientes=sin_entregar)
            if not motivo:
                raise ReglaCuenta('Indicar el motivo para cerrar la mesa con pedidos sin entregar.', estado=400)
            from .comensales import resolver_comandas_sin_entregar   # import tardio: comensales importa este modulo
            resolver_comandas_sin_entregar(sesion, empleado, f'cierre de mesa forzado: {motivo}')

        total = total_de_sesion(sesion)
        pagada = factura is not None and factura.estado == 'Pagada'
        forzado = False
        if total > 0 and not pagada:
            saldo = saldo_de_factura(factura) if factura is not None else total
            if not forzar:
                raise ReglaCuenta('La mesa tiene consumo sin pagar. Cobrar la cuenta antes de cerrarla.',
                                  total=str(total), saldo=str(saldo), factura=factura.id if factura else None)
            if not es_admin_o_gerente:
                raise ReglaCuenta('Solo un Admin o Gerente puede cerrar una mesa con saldo pendiente.', estado=403)
            if not motivo:
                raise ReglaCuenta('Indicar el motivo para cerrar la mesa con saldo pendiente.', estado=400)
            forzado = True
            if factura is not None and factura.estado == 'Emitida' and not Pago.objects.filter(factura=factura, estado='Aprobado').exists():
                Factura.objects.filter(pk=factura.pk).update(
                    estado='Anulada', fecha_hora_anulacion=timezone.now(), empleado_anulacion=empleado,
                    motivo_anulacion=f'Cierre de mesa forzado: {motivo}'[:200])

        sesion.estado = 'Cerrado'
        sesion.fecha_hora_cierre = timezone.now()
        sesion.cierre_forzado = forzado
        sesion.motivo_cierre = motivo[:200] if forzado else None
        sesion.empleado_cierre = empleado
        sesion.save(update_fields=['estado', 'fecha_hora_cierre', 'cierre_forzado', 'motivo_cierre', 'empleado_cierre'])
        mesa = sesion.mesa
        mesa.estado = False
        mesa.save(update_fields=['estado'])
    return sesion


# ---------- como se ve la cuenta ----------

def armar_cuenta(sesion):
    """Todo lo que hay que mostrar de la cuenta de una sesion (valores crudos: Decimal y datetime; la vista los serializa).
    Sin factura es una VISTA PREVIA del consumo; con factura, lo congelado al emitirla."""
    detalles = detalles_de_sesion(sesion)
    factura = factura_vigente(sesion)
    consumo = sum((d.sub_total for d in detalles), CERO)
    renglones_desglose = [
        {'sub_total': d.sub_total, 'comensal': d.identificador_comensal, 'compartido': [c.participante for c in d.compartido.all()]}
        for d in detalles
    ]
    if factura is not None:
        total = factura.total
        pagos = list(Pago.objects.filter(factura=factura).select_related('metodo_pago', 'empleado').order_by('id'))
        saldo = saldo_de_la_cuenta(total, [{'estado': p.estado, 'monto': p.monto} for p in pagos])
        eq = {'USD': factura.total_usd, 'BRL': factura.total_brl, 'PYG': factura.total_pyg}
        renglones = [
            {'descripcion': r.descripcion, 'cantidad': r.cantidad, 'precio_unitario': r.precio_unitario,
             'sub_total': r.sub_total, 'comensal': r.identificador_comensal}
            for r in FacturaDetalle.objects.filter(factura=factura).order_by('id')
        ]
    else:
        total = consumo
        pagos = []
        saldo = consumo
        eq = equivalentes(consumo, cotizaciones_vigentes()) if consumo > 0 else {'USD': None, 'BRL': None, 'PYG': None}
        renglones = [
            {'descripcion': descripcion_de_renglon(d.producto.nombre, nombres_quitados(d), texto_extras(d)), 'cantidad': d.cantidad,
             'precio_unitario': d.precio_unitario, 'sub_total': d.sub_total, 'comensal': d.identificador_comensal}
            for d in detalles
        ]
    bloqueos = comandas_en_cocina(sesion) if sesion.estado == 'Abierto' else []
    return {
        'sesion': sesion, 'factura': factura, 'estado_cuenta': factura.estado if factura else 'Sin emitir',
        'total': total, 'saldo': saldo, 'equivalentes': eq, 'renglones': renglones, 'pagos': pagos,
        'por_comensal': desglose_por_comensal(renglones_desglose),
        'comandas_en_cocina': bloqueos,
        'puede_cobrarse': sesion.estado == 'Abierto' and total > 0 and not bloqueos and saldo > 0,
        'en_sobremesa': sesion.estado == 'Abierto' and factura is not None and factura.estado == 'Pagada',
        'caja_abierta': caja_abierta() is not None,
    }


def propinas_por_mozo(desde=None, hasta=None, empleado_id=None):
    """Propinas de pagos Aprobados por mozo: [{'empleado_id', 'empleado', 'propina_total', 'pagos'}]. Todo en pesos."""
    pagos = Pago.objects.filter(estado='Aprobado', monto_propina__gt=0).select_related('empleado_propina')
    if desde:
        pagos = pagos.filter(fecha_hora__gte=desde)
    if hasta:
        pagos = pagos.filter(fecha_hora__lt=hasta)
    if empleado_id:
        pagos = pagos.filter(empleado_propina_id=empleado_id)
    acumulado = {}
    for pago in pagos:
        mozo = pago.empleado_propina
        fila = acumulado.setdefault(mozo.id, {'empleado_id': mozo.id, 'empleado': f'{mozo.nombre} {mozo.apellido}',
                                              'propina_total': CERO, 'pagos': 0})
        fila['propina_total'] += pago.monto_propina
        fila['pagos'] += 1
    return sorted(acumulado.values(), key=lambda f: f['empleado'])
