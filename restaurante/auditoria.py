"""Linea de tiempo de auditoria de cobros (hito 6): una sola lista, de lo mas nuevo a lo mas viejo, armada con lo que ya queda
registrado al cobrar. No hay tablas nuevas ni nada que se escriba de mas:
  pago        PagoEvento      cada cambio de un pago (cobro iniciado, aprobado, anulado, vencido, aprobacion tardia...)
  movimiento  MovimientoCaja  cada ingreso o egreso de la caja (venta, propina, vuelto, anulacion, manual)
  caja        Caja            apertura y cierre (con lo esperado, lo declarado y la diferencia)
  factura     Factura         emision y anulacion
  mesa        PedidoCabecera  cierres de mesa FORZADOS (con saldo pendiente), con el motivo

Filtros que no aplican a una fuente la dejan afuera (ej.: con `caja` solo salen movimientos y aperturas/cierres de esa caja,
porque un pago o una factura no pertenecen a una caja)."""
from datetime import datetime, time, timedelta

from django.utils import timezone

from .auditoria_calculos import (
    evento_de_caja, evento_de_factura, evento_de_mesa, evento_de_movimiento, evento_de_pago, incluye, mezclar,
)
from .models import Caja, Factura, MovimientoCaja, PagoEvento, PedidoCabecera


def _persona(empleado):
    return {'id': empleado.id, 'nombre': f'{empleado.nombre} {empleado.apellido}'} if empleado else None


def _local(valor):
    return timezone.localtime(valor) if valor is not None and timezone.is_aware(valor) else valor


def _limites(filtros):
    """(desde, hasta_exclusivo) como fechas con hora de la zona del local, o None."""
    zona = timezone.get_current_timezone()
    desde = hasta = None
    if filtros['desde']:
        desde = timezone.make_aware(datetime.combine(filtros['desde'], time.min), zona)
    if filtros['hasta']:
        hasta = timezone.make_aware(datetime.combine(filtros['hasta'] + timedelta(days=1), time.min), zona)
    return desde, hasta


def _en_rango(campo, filtros):
    desde, hasta = _limites(filtros)
    condiciones = {}
    if desde:
        condiciones[f'{campo}__gte'] = desde
    if hasta:
        condiciones[f'{campo}__lt'] = hasta
    return condiciones


def _traer(consulta, campo, cuantos):
    return list(consulta.order_by(f'-{campo}', '-id')[:cuantos])


# ---------- una consulta por fuente ----------

def _pagos(filtros, cuantos):
    if filtros['caja']:
        return []
    consulta = PagoEvento.objects.select_related(
        'empleado', 'pago__metodo_pago', 'pago__factura__pedido_cabecera__mesa',
    ).filter(**_en_rango('fecha_hora', filtros))
    if filtros['empleado']:
        consulta = consulta.filter(empleado_id=filtros['empleado'])
    if filtros['mesa']:
        consulta = consulta.filter(pago__factura__pedido_cabecera__mesa__numero=filtros['mesa'])
    if filtros['factura']:
        consulta = consulta.filter(pago__factura_id=filtros['factura'])
    if filtros['pago']:
        consulta = consulta.filter(pago_id=filtros['pago'])
    eventos = []
    for e in _traer(consulta, 'fecha_hora', cuantos):
        pago = e.pago
        eventos.append(evento_de_pago({
            'fecha_hora': _local(e.fecha_hora), 'evento': e.evento, 'estado_anterior': e.estado_anterior,
            'estado_nuevo': e.estado_nuevo, 'detalle': e.detalle, 'empleado': _persona(e.empleado),
            'mesa': pago.factura.pedido_cabecera.mesa.numero, 'factura': pago.factura_id, 'pago': pago.id,
            'medio': pago.metodo_pago.nombre, 'monto': pago.monto,
        }))
    return eventos


def _movimientos(filtros, cuantos):
    consulta = MovimientoCaja.objects.select_related(
        'empleado', 'pago__factura__pedido_cabecera__mesa',
    ).filter(**_en_rango('fecha_hora', filtros))
    if filtros['empleado']:
        consulta = consulta.filter(empleado_id=filtros['empleado'])
    if filtros['caja']:
        consulta = consulta.filter(caja_id=filtros['caja'])
    if filtros['mesa']:
        consulta = consulta.filter(pago__factura__pedido_cabecera__mesa__numero=filtros['mesa'])
    if filtros['factura']:
        consulta = consulta.filter(pago__factura_id=filtros['factura'])
    if filtros['pago']:
        consulta = consulta.filter(pago_id=filtros['pago'])
    eventos = []
    for m in _traer(consulta, 'fecha_hora', cuantos):
        pago = m.pago
        eventos.append(evento_de_movimiento({
            'fecha_hora': _local(m.fecha_hora), 'tipo': m.tipo, 'concepto': m.concepto, 'medio': m.medio,
            'moneda': m.moneda, 'monto': m.monto, 'descripcion': m.descripcion, 'empleado': _persona(m.empleado),
            'caja': m.caja_id, 'pago': pago.id if pago else None,
            'mesa': pago.factura.pedido_cabecera.mesa.numero if pago else None,
            'factura': pago.factura_id if pago else None,
        }))
    return eventos


def _cajas(filtros, cuantos):
    if filtros['mesa'] or filtros['factura'] or filtros['pago']:
        return []
    base = Caja.objects.select_related('empleado_apertura', 'empleado_cierre')
    if filtros['caja']:
        base = base.filter(pk=filtros['caja'])
    abiertas = base.filter(**_en_rango('fecha_hora_apertura', filtros))
    cerradas = base.filter(fecha_hora_cierre__isnull=False, **_en_rango('fecha_hora_cierre', filtros))
    if filtros['empleado']:
        abiertas = abiertas.filter(empleado_apertura_id=filtros['empleado'])
        cerradas = cerradas.filter(empleado_cierre_id=filtros['empleado'])
    eventos = []
    for c in _traer(abiertas, 'fecha_hora_apertura', cuantos):
        eventos.append(evento_de_caja({
            'caja': c.id, 'fecha_hora': _local(c.fecha_hora_apertura), 'empleado': _persona(c.empleado_apertura),
        }, cierre=False))
    for c in _traer(cerradas, 'fecha_hora_cierre', cuantos):
        eventos.append(evento_de_caja({
            'caja': c.id, 'fecha_hora': _local(c.fecha_hora_cierre), 'empleado': _persona(c.empleado_cierre),
            'esperado': c.total_esperado_ars, 'declarado': c.total_declarado_ars,
        }, cierre=True))
    return eventos


def _facturas(filtros, cuantos):
    if filtros['caja'] or filtros['pago']:
        return []
    base = Factura.objects.select_related('empleado', 'empleado_anulacion', 'pedido_cabecera__mesa')
    if filtros['factura']:
        base = base.filter(pk=filtros['factura'])
    if filtros['mesa']:
        base = base.filter(pedido_cabecera__mesa__numero=filtros['mesa'])
    emitidas = base.filter(**_en_rango('fecha_hora_emision', filtros))
    anuladas = base.filter(fecha_hora_anulacion__isnull=False, **_en_rango('fecha_hora_anulacion', filtros))
    if filtros['empleado']:
        emitidas = emitidas.filter(empleado_id=filtros['empleado'])
        anuladas = anuladas.filter(empleado_anulacion_id=filtros['empleado'])
    eventos = []
    for f in _traer(emitidas, 'fecha_hora_emision', cuantos):
        eventos.append(evento_de_factura({
            'fecha_hora': _local(f.fecha_hora_emision), 'empleado': _persona(f.empleado),
            'mesa': f.pedido_cabecera.mesa.numero, 'factura': f.id, 'total': f.total,
        }, anulacion=False))
    for f in _traer(anuladas, 'fecha_hora_anulacion', cuantos):
        eventos.append(evento_de_factura({
            'fecha_hora': _local(f.fecha_hora_anulacion), 'empleado': _persona(f.empleado_anulacion),
            'mesa': f.pedido_cabecera.mesa.numero, 'factura': f.id, 'total': f.total, 'motivo': f.motivo_anulacion,
        }, anulacion=True))
    return eventos


def _mesas(filtros, cuantos):
    if filtros['caja'] or filtros['factura'] or filtros['pago']:
        return []
    consulta = PedidoCabecera.objects.select_related('mesa', 'empleado_cierre').filter(
        cierre_forzado=True, fecha_hora_cierre__isnull=False, **_en_rango('fecha_hora_cierre', filtros))
    if filtros['empleado']:
        consulta = consulta.filter(empleado_cierre_id=filtros['empleado'])
    if filtros['mesa']:
        consulta = consulta.filter(mesa__numero=filtros['mesa'])
    return [
        evento_de_mesa({
            'fecha_hora': _local(s.fecha_hora_cierre), 'empleado': _persona(s.empleado_cierre),
            'mesa': s.mesa.numero, 'motivo': s.motivo_cierre,
        })
        for s in _traer(consulta, 'fecha_hora_cierre', cuantos)
    ]


FUENTES = (('pago', _pagos), ('movimiento', _movimientos), ('caja', _cajas), ('factura', _facturas), ('mesa', _mesas))


def linea_de_tiempo(filtros):
    """{'eventos': [...], 'hay_mas': bool}. Cada fuente trae solo los `desplazamiento + limite + 1` eventos mas nuevos que
    cumplen el filtro: alcanza para que el orden y la pagina sean exactos sin leer toda la historia."""
    cuantos = filtros['desplazamiento'] + filtros['limite'] + 1
    listas = [consulta(filtros, cuantos) for tipo, consulta in FUENTES if incluye(filtros, tipo)]
    eventos, hay_mas = mezclar(listas, filtros['limite'], filtros['desplazamiento'])
    return {'eventos': eventos, 'hay_mas': hay_mas}
