"""
Jornada: periodo en que el local esta abierto al publico.

- Una sola jornada abierta a la vez (lo garantiza un indice unico en la base).
- Sin jornada abierta no se abren mesas ni se aceptan comandas; cobrar, el stock y lo administrativo siguen disponibles.
- Los horarios de los turnos SUGIEREN el turno al abrir y AVISAN cuando conviene cerrar,
  pero nunca abren ni cierran nada solos: el que manda es el boton.
"""
from datetime import datetime, timedelta

from django.utils import timezone

from .models import Jornada, Turno


def jornada_abierta():
    return Jornada.objects.select_related('turno').filter(estado='Abierta').first()


def turno_contiene(turno, hora):
    """True si la hora (datetime.time local) cae dentro del horario del turno."""
    apertura, cierre = turno.hora_apertura, turno.hora_cierre
    if apertura < cierre:
        return apertura <= hora < cierre
    return hora >= apertura or hora < cierre  # el turno cruza la medianoche


def turno_sugerido(ahora=None):
    """Turno activo cuyo horario incluye la hora actual (o None si ninguno)."""
    ahora = timezone.localtime(ahora or timezone.now())
    for turno in Turno.objects.filter(activo=True).order_by('hora_apertura', 'id'):
        if turno_contiene(turno, ahora.time()):
            return turno
    return None


def cierre_previsto(jornada):
    """Fecha y hora (local) en que termina el horario del turno de esta jornada, contando desde que se abrio."""
    apertura = timezone.localtime(jornada.fecha_hora_apertura)
    candidato = datetime.combine(apertura.date(), jornada.turno.hora_cierre, tzinfo=apertura.tzinfo)
    if candidato <= apertura:
        candidato += timedelta(days=1)
    return candidato


def sugerir_cierre(jornada, ahora=None):
    """True si la jornada sigue abierta pasado el horario previsto de cierre. Solo es un aviso."""
    if jornada.estado != 'Abierta':
        return False
    return (ahora or timezone.now()) > cierre_previsto(jornada)


def _rango(turno):
    return f"{turno.hora_apertura.strftime('%H:%M')} a {turno.hora_cierre.strftime('%H:%M')}"


def advertencia_apertura(turno, ahora=None):
    """Aviso (texto) si se abre un turno fuera de su horario; None si la hora cae dentro. Es solo un aviso:
    el Gerente puede abrir cuando quiera (para prepararse antes, o para probar el sistema)."""
    ahora = timezone.localtime(ahora or timezone.now())
    if turno_contiene(turno, ahora.time()):
        return None
    return (f'Se abrio el turno {turno.nombre} fuera de su horario ({_rango(turno)}); '
            f'son las {ahora.strftime("%H:%M")}.')


def advertencia_cierre(jornada, ahora=None):
    """Aviso (texto) si se cierra la jornada antes del horario previsto de cierre; None si no."""
    ahora = ahora or timezone.now()
    if ahora >= cierre_previsto(jornada):
        return None
    return (f'Se cerro la jornada antes del horario previsto del turno {jornada.turno.nombre} '
            f'({_rango(jornada.turno)}).')


def duracion_segundos(jornada, ahora=None):
    """Tiempo transcurrido desde la apertura hasta el cierre (o hasta ahora si sigue abierta)."""
    fin = jornada.fecha_hora_cierre or ahora or timezone.now()
    return max(0, int((fin - jornada.fecha_hora_apertura).total_seconds()))
