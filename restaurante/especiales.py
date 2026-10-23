"""
Especiales (promos) por dia.

Capas, de menor a mayor prioridad:
  1. Regla SEMANAL  : "todos los martes, este plato a este precio" (Especial.dia_semana, 1=lunes ... 7=domingo).
  2. Excepcion por FECHA : un plato especial solo para una fecha puntual (Especial.fecha).
     La fecha puede estar configurada (DiaEspecial) para REEMPLAZAR los especiales semanales de ese dia
     o para SUMARSE a ellos. Si un plato esta en las dos capas (y los turnos se superponen), gana la fecha.

Cada especial puede limitarse a un turno (almuerzo, cena); sin turno vale todo el dia.
Que dia y que turno valen lo define la JORNADA abierta (no el reloj): una jornada abierta el viernes a las 20
sigue usando los especiales del viernes pasada la medianoche. Sin jornada abierta no hay especiales vigentes.
"""
import calendar
from datetime import date

from .jornadas import jornada_abierta
from .models import Especial, DiaEspecial


def _se_solapan(turno_a, turno_b):
    """Dos turnos se superponen si alguno es 'todo el dia' (None) o son el mismo."""
    return turno_a is None or turno_b is None or turno_a == turno_b


def _resolver(semanales, puntuales, config):
    """Aplica las capas. Devuelve una lista de (Especial, origen) con origen 'semanal' o 'fecha'."""
    if config is not None and config.reemplaza:
        semanales = []
    else:
        semanales = [
            s for s in semanales
            if not any(p.producto_id == s.producto_id and _se_solapan(p.turno_id, s.turno_id) for p in puntuales)
        ]
    return [(s, 'semanal') for s in semanales] + [(p, 'fecha') for p in puntuales]


def _base():
    return Especial.objects.select_related('producto', 'turno').filter(producto__activo=True)


def especiales_de_fecha(fecha):
    """Especiales vigentes en una fecha (todos los turnos), ya resueltas las capas."""
    semanales = list(_base().filter(dia_semana=fecha.isoweekday()))
    puntuales = list(_base().filter(fecha=fecha))
    config = DiaEspecial.objects.filter(fecha=fecha).first()
    return _resolver(semanales, puntuales, config)


def calendario_mes(anio, mes):
    """Un elemento por dia del mes: {'fecha', 'config' (DiaEspecial o None), 'especiales': [(Especial, origen)]}."""
    ultimo = calendar.monthrange(anio, mes)[1]
    desde, hasta = date(anio, mes, 1), date(anio, mes, ultimo)
    semanales = list(_base().filter(dia_semana__isnull=False))
    puntuales = list(_base().filter(fecha__gte=desde, fecha__lte=hasta))
    configs = {c.fecha: c for c in DiaEspecial.objects.filter(fecha__gte=desde, fecha__lte=hasta)}

    dias = []
    for numero in range(1, ultimo + 1):
        fecha = date(anio, mes, numero)
        del_dia = [s for s in semanales if s.dia_semana == fecha.isoweekday()]
        de_fecha = [p for p in puntuales if p.fecha == fecha]
        config = configs.get(fecha)
        dias.append({'fecha': fecha, 'config': config, 'especiales': _resolver(del_dia, de_fecha, config)})
    return dias


def precios_especiales(fecha, id_turno):
    """{id_producto: precio especial} para esa fecha y ese turno."""
    precios = {}
    for especial, _origen in especiales_de_fecha(fecha):
        if especial.turno_id is None or especial.turno_id == id_turno:
            actual = precios.get(especial.producto_id)
            precios[especial.producto_id] = especial.precio_especial if actual is None else min(actual, especial.precio_especial)
    return precios


def precios_especiales_vigentes():
    """Especiales de la jornada abierta ahora. Sin jornada abierta: ninguno."""
    jornada = jornada_abierta()
    if jornada is None:
        return {}
    return precios_especiales(jornada.fecha, jornada.turno_id)


def precio_a_cobrar(producto, precios):
    """Precio que se le cobra al cliente: el especial si hay uno, pero nunca mas que el precio normal."""
    especial = precios.get(producto.id)
    if especial is None:
        return producto.precio_actual
    return min(producto.precio_actual, especial)
