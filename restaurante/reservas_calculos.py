"""Reglas puras de las reservas (sin Django ni base de datos, para poder probarlas solas).

Una reserva es de una JORNADA (fecha + turno) y bloquea la mesa toda la jornada. No tiene duracion. La hora es la de llegada
acordada; pasada la tolerancia sin que el cliente aparezca, el sistema la marca "No se presentó" y la mesa queda libre.
Todas las fechas y horas de este modulo son locales y sin zona (datetime ingenuos): la conversion la hace reservas.py.
"""
import re
from datetime import datetime, timedelta

TOLERANCIA_MINUTOS_DEFECTO = 30

CONFIRMADA = 'Confirmada'
CANCELADA = 'Cancelada'
CUMPLIDA = 'Cumplida'
NO_SE_PRESENTO = 'No se presentó'
ESTADOS = (CONFIRMADA, CANCELADA, CUMPLIDA, NO_SE_PRESENTO)

ORIGENES = ('Llamada', 'Mensaje', 'Otro')

_TELEFONO = re.compile(r'^[0-9+()\- ]{6,20}$')


def turno_cruza_medianoche(apertura, cierre):
    """El turno termina al dia siguiente si su cierre es menor o igual a su apertura (ej.: Cena 20:00 a 00:30)."""
    return cierre <= apertura


def hora_en_turno(apertura, cierre, hora):
    """True si la hora (datetime.time) cae dentro del horario del turno."""
    if apertura < cierre:
        return apertura <= hora < cierre
    return hora >= apertura or hora < cierre


def momento_llegada(fecha, hora, apertura, cierre):
    """Fecha y hora reales de llegada. En un turno que cruza la medianoche, una hora anterior a la apertura (ej.: 00:15 en la
    Cena) pertenece al dia siguiente de la fecha de la jornada."""
    llegada = datetime.combine(fecha, hora)
    if turno_cruza_medianoche(apertura, cierre) and hora < apertura:
        llegada += timedelta(days=1)
    return llegada


def limite_de_llegada(llegada, tolerancia_minutos=TOLERANCIA_MINUTOS_DEFECTO):
    """Hasta cuando se espera al cliente."""
    return llegada + timedelta(minutes=tolerancia_minutos)


def esta_vencida(llegada, ahora, tolerancia_minutos=TOLERANCIA_MINUTOS_DEFECTO):
    """True si ya paso la hora de llegada mas la tolerancia (el cliente no se presento)."""
    return ahora > limite_de_llegada(llegada, tolerancia_minutos)


def limpiar_telefono(texto):
    """Devuelve el telefono sin espacios de los costados, o lanza ValueError con el motivo."""
    limpio = (texto or '').strip()
    if not _TELEFONO.match(limpio) or sum(c.isdigit() for c in limpio) < 6:
        raise ValueError('El teléfono debe tener entre 6 y 20 caracteres: números, espacios, +, - o paréntesis.')
    return limpio


def elegir_mesa(candidatas, personas):
    """Mesa mas chica que alcance para las personas (a igual capacidad, la de numero menor).
    `candidatas` es una lista de (numero, capacidad). Devuelve el numero o None."""
    aptas = [(capacidad, numero) for numero, capacidad in candidatas if capacidad >= personas]
    return min(aptas)[1] if aptas else None


def texto_hora(hora):
    return hora.strftime('%H:%M')


def mensaje_mesa_reservada(numero_mesa, nombre, apellido, turno, hora):
    """Lo que ve el mozo al intentar abrir una mesa que tiene una reserva en la jornada."""
    return (f'La mesa {numero_mesa} está reservada a nombre de {nombre} {apellido} para el turno {turno} '
            f'(llegada a las {texto_hora(hora)}). Solo se puede abrir para esa reserva.')


def mensaje_mesa_ocupada_para_reservar(numero_mesa):
    return f'La mesa {numero_mesa} está ocupada en este momento: no se puede reservar para la jornada que está en curso.'


def mensaje_reserva_existente(numero_mesa, nombre, apellido, turno, fecha):
    return (f'La mesa {numero_mesa} ya está reservada para el turno {turno} del {fecha.strftime("%d/%m/%Y")} '
            f'a nombre de {nombre} {apellido}. Elegí otra mesa, otro turno u otra fecha.')
