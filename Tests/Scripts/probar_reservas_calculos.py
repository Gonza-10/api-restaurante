"""Pruebas de restaurante/reservas_calculos.py (no necesitan Django, base de datos ni internet).

Uso (desde la raiz del repo):  python Tests/Scripts/probar_reservas_calculos.py
"""
import os
import sys
from datetime import date, datetime, time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from restaurante.reservas_calculos import (  # noqa: E402
    CANCELADA, CONFIRMADA, CUMPLIDA, ESTADOS, NO_SE_PRESENTO, elegir_mesa, esta_vencida, hora_en_turno, limite_de_llegada,
    limpiar_telefono, mensaje_mesa_reservada, mensaje_reserva_existente, momento_llegada, texto_hora, turno_cruza_medianoche,
)

total = 0
fallos = []


def comprobar(nombre, condicion):
    global total
    total += 1
    if not condicion:
        fallos.append(nombre)
        print(f'  FALLA: {nombre}')


ALMUERZO = (time(10, 0), time(15, 0))
CENA = (time(20, 0), time(0, 30))   # cruza la medianoche

# ---------- estados ----------
comprobar('cuatro estados, en espanol', ESTADOS == ('Confirmada', 'Cancelada', 'Cumplida', 'No se presentó'))
comprobar('el estado automatico se llama "No se presentó"', NO_SE_PRESENTO == 'No se presentó')
comprobar('no hay estados en ingles', not any('show' in e.lower() for e in ESTADOS))

# ---------- horario del turno ----------
comprobar('almuerzo no cruza la medianoche', not turno_cruza_medianoche(*ALMUERZO))
comprobar('cena cruza la medianoche', turno_cruza_medianoche(*CENA))
comprobar('13:00 esta en el almuerzo', hora_en_turno(*ALMUERZO, time(13, 0)))
comprobar('10:00 esta en el almuerzo (apertura inclusiva)', hora_en_turno(*ALMUERZO, time(10, 0)))
comprobar('15:00 ya no (cierre exclusivo)', not hora_en_turno(*ALMUERZO, time(15, 0)))
comprobar('09:59 no esta en el almuerzo', not hora_en_turno(*ALMUERZO, time(9, 59)))
comprobar('21:00 esta en la cena', hora_en_turno(*CENA, time(21, 0)))
comprobar('00:15 esta en la cena (pasada la medianoche)', hora_en_turno(*CENA, time(0, 15)))
comprobar('00:30 ya no esta en la cena', not hora_en_turno(*CENA, time(0, 30)))
comprobar('13:00 no esta en la cena', not hora_en_turno(*CENA, time(13, 0)))

# ---------- momento de llegada ----------
f = date(2026, 11, 20)
comprobar('llegada 21:00 de la cena es ese mismo dia', momento_llegada(f, time(21, 0), *CENA) == datetime(2026, 11, 20, 21, 0))
comprobar('llegada 00:15 de la cena es el dia siguiente', momento_llegada(f, time(0, 15), *CENA) == datetime(2026, 11, 21, 0, 15))
comprobar('llegada 13:00 del almuerzo es ese dia', momento_llegada(f, time(13, 0), *ALMUERZO) == datetime(2026, 11, 20, 13, 0))
comprobar('llegada a las 20:00 (apertura de la cena) es ese dia', momento_llegada(f, time(20, 0), *CENA) == datetime(2026, 11, 20, 20, 0))

# ---------- tolerancia de 30 minutos ----------
llegada = datetime(2026, 11, 20, 21, 0)
comprobar('limite = llegada + 30 min', limite_de_llegada(llegada) == datetime(2026, 11, 20, 21, 30))
comprobar('a las 21:00 no esta vencida', not esta_vencida(llegada, datetime(2026, 11, 20, 21, 0)))
comprobar('a las 21:29 no esta vencida', not esta_vencida(llegada, datetime(2026, 11, 20, 21, 29)))
comprobar('a las 21:30 justo todavia se espera', not esta_vencida(llegada, datetime(2026, 11, 20, 21, 30)))
comprobar('a las 21:31 vence', esta_vencida(llegada, datetime(2026, 11, 20, 21, 31)))
comprobar('un dia despues vence', esta_vencida(llegada, datetime(2026, 11, 21, 12, 0)))
comprobar('antes de la hora no esta vencida', not esta_vencida(llegada, datetime(2026, 11, 20, 12, 0)))
comprobar('la tolerancia es configurable (10 min)', esta_vencida(llegada, datetime(2026, 11, 20, 21, 11), 10))
cruza = momento_llegada(f, time(0, 15), *CENA)
comprobar('cena 00:15: a las 23:50 del mismo dia no esta vencida', not esta_vencida(cruza, datetime(2026, 11, 20, 23, 50)))
comprobar('cena 00:15: a las 00:46 del dia siguiente vence', esta_vencida(cruza, datetime(2026, 11, 21, 0, 46)))

# ---------- telefono ----------
comprobar('telefono normal', limpiar_telefono(' 3764 123456 ') == '3764 123456')
comprobar('telefono con +54 y guiones', limpiar_telefono('+54 376-4123456') == '+54 376-4123456')
for malo in ('', None, '123', 'abcdefgh', '12345', '3764-ABC-123', '1' * 25):
    try:
        limpiar_telefono(malo)
        comprobar(f'telefono invalido {malo!r} se rechaza', False)
    except ValueError:
        comprobar(f'telefono invalido {malo!r} se rechaza', True)

# ---------- eleccion de mesa ----------
mesas = [(1, 2), (2, 4), (3, 4), (4, 6)]
comprobar('2 personas: la mesa de 2', elegir_mesa(mesas, 2) == 1)
comprobar('3 personas: la mas chica que alcance (la 2 de 4)', elegir_mesa(mesas, 3) == 2)
comprobar('4 personas: a igual capacidad, la de numero menor', elegir_mesa(mesas, 4) == 2)
comprobar('5 personas: la de 6', elegir_mesa(mesas, 5) == 4)
comprobar('7 personas: ninguna', elegir_mesa(mesas, 7) is None)
comprobar('sin candidatas: ninguna', elegir_mesa([], 2) is None)
comprobar('con la mesa chica tomada, 2 personas va a la de 4', elegir_mesa(mesas[1:], 2) == 2)

# ---------- mensajes ----------
m = mensaje_mesa_reservada(7, 'Fernando', 'Pérez', 'Cena', time(21, 0))
comprobar('el mensaje del mozo nombra mesa, cliente, turno y hora',
          all(t in m for t in ('mesa 7', 'Fernando Pérez', 'Cena', '21:00')))
comprobar('el mensaje del mozo dice que solo se abre para esa reserva', 'Solo se puede abrir para esa reserva' in m)
e = mensaje_reserva_existente(2, 'Ana', 'Gómez', 'Almuerzo', date(2026, 11, 22))
comprobar('el mensaje de reserva existente tiene la fecha en formato argentino', '22/11/2026' in e and 'Ana Gómez' in e)
comprobar('texto_hora', texto_hora(time(9, 5)) == '09:05')

print(f'\n{total - len(fallos)} de {total} chequeos correctos.')
if fallos:
    print('FALLARON:', ', '.join(fallos))
    sys.exit(1)
