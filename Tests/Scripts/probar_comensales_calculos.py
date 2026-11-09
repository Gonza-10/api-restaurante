"""Pruebas de comensales y seguridad de la mesa (restaurante/comensales_calculos.py). No necesitan Django, base de datos ni internet.

Uso (desde la raiz del repo):  python Tests/Scripts/probar_comensales_calculos.py
"""
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal as D

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from restaurante.comensales_calculos import (  # noqa: E402
    ACTIVO, RETIRADO, agregar_pin_anterior, clave_nombre, comandas_a_cancelar, estado_inicial_de_comanda,
    estados_que_bloquean_el_cierre, faltan_por_ok, limpiar_nombre, modalidad_valida, pin_fue_anterior, plan_devolucion,
    segundos_para_regenerar, texto_motivo_cancelacion, todos_dieron_ok,
)

total = 0
fallos = []


def comprobar(nombre, condicion):
    global total
    total += 1
    if not condicion:
        fallos.append(nombre)
        print(f'  FALLA: {nombre}')


def da_error(nombre, funcion, *args):
    try:
        funcion(*args)
    except ValueError:
        comprobar(nombre, True)
    else:
        comprobar(nombre, False)


# ---------- modalidad ----------
comprobar('modalidad Familiar', modalidad_valida('familiar') == 'Familiar')
comprobar('modalidad Grupal con espacios y mayusculas', modalidad_valida('  GRUPAL ') == 'Grupal')
comprobar('modalidad invalida', modalidad_valida('amigos') is None)
comprobar('modalidad vacia', modalidad_valida(None) is None)

# ---------- nombres ----------
comprobar('nombre sin espacios de mas', limpiar_nombre('  Ana   María ') == 'Ana María')
da_error('nombre vacio', limpiar_nombre, '   ')
da_error('nombre largo', limpiar_nombre, 'x' * 51)
da_error('nombre con caracter de control', limpiar_nombre, 'Ana\x00')
comprobar('nombre de 50 caracteres', limpiar_nombre('x' * 50) == 'x' * 50)
comprobar('clave ignora mayusculas', clave_nombre('ANA') == clave_nombre('ana'))
comprobar('clave ignora acentos', clave_nombre('María') == clave_nombre('maria'))
comprobar('clave ignora espacios repetidos', clave_nombre('Ana  Paz') == clave_nombre('ana paz'))
comprobar('claves distintas', clave_nombre('Ana') != clave_nombre('Anita'))

# ---------- estado inicial de la comanda ----------
comprobar('grupal antes de la primera ronda: retenida', estado_inicial_de_comanda('Grupal', False) == 'retenida')
comprobar('grupal con la ronda liberada: pendiente', estado_inicial_de_comanda('Grupal', True) == 'pendiente')
comprobar('familiar nunca espera', estado_inicial_de_comanda('Familiar', False) == 'pendiente')

# ---------- OK de todos ----------
comprobar('todos con OK', todos_dieron_ok([(ACTIVO, True), (ACTIVO, True)]))
comprobar('falta uno', not todos_dieron_ok([(ACTIVO, True), (ACTIVO, False)]))
comprobar('el retirado no cuenta', todos_dieron_ok([(ACTIVO, True), (RETIRADO, False)]))
comprobar('sin comensales activos no se libera', not todos_dieron_ok([]))
comprobar('solo retirados no se libera', not todos_dieron_ok([(RETIRADO, True)]))
comprobar('faltan por ok', faltan_por_ok([('Ana', ACTIVO, True), ('Beto', ACTIVO, False), ('Cami', RETIRADO, False)]) == ['Beto'])
comprobar('no falta nadie', faltan_por_ok([('Ana', ACTIVO, True)]) == [])

# ---------- que se cancela cuando alguien se va ----------
comandas = [
    (1, 10, 'retenida'),   # de Ana, sin salir a cocina
    (2, 10, 'pendiente'),  # de Ana, pendiente
    (3, 10, 'proceso'),    # de Ana, en preparacion: queda en la cuenta
    (4, 10, 'listo'),      # de Ana, lista: queda
    (5, 10, None),         # de Ana, entregada: queda
    (6, 11, 'pendiente'),  # de Beto: no se va
    (7, None, 'pendiente'),  # sin comensal
]
comprobar('se cancelan retenida y pendiente de quien se fue', comandas_a_cancelar(comandas, {10}) == [1, 2])
comprobar('nadie marcado: no se cancela nada', comandas_a_cancelar(comandas, set()) == [])
comprobar('no toca las de otros', comandas_a_cancelar(comandas, {11}) == [6])
comprobar('dos comensales', comandas_a_cancelar(comandas, {10, 11}) == [1, 2, 6])
comprobar('comanda sin comensal no se cancela por nadie', 7 not in comandas_a_cancelar(comandas, {10, 11}))

# ---------- cierre de mesa ----------
comprobar('bloquean el cierre', estados_que_bloquean_el_cierre(['retenida', 'pendiente', 'proceso', 'listo']) ==
          ['retenida', 'pendiente', 'proceso', 'listo'])
comprobar('entregada no bloquea', estados_que_bloquean_el_cierre([None, 'entregado']) == [])
comprobar('mezcla', estados_que_bloquean_el_cierre([None, 'proceso', 'entregado']) == ['proceso'])

# ---------- devolucion de stock ----------
consumo = [(1, 'Consumo', D('-200.000')), (2, 'Consumo', D('-50.000')), (1, 'Consumo', D('-100.000'))]
comprobar('devuelve lo consumido por lote', plan_devolucion(consumo) == {1: D('300.000'), 2: D('50.000')})
parcial = consumo + [(1, 'Devolucion', D('300.000'))]
comprobar('lo ya devuelto no se devuelve de nuevo', plan_devolucion(parcial) == {2: D('50.000')})
todo = parcial + [(2, 'Devolucion', D('50.000'))]
comprobar('devuelto todo: no hay nada', plan_devolucion(todo) == {})
comprobar('otros tipos se ignoran', plan_devolucion([(1, 'Perdida', D('-5')), (1, 'Consumo', D('-10'))]) == {1: D('10')})
comprobar('sin movimientos', plan_devolucion([]) == {})

# ---------- PIN ----------
ahora = datetime(2026, 11, 9, 20, 0, 0)
comprobar('sin cambios previos se puede', segundos_para_regenerar(None, ahora) == 0)
comprobar('recien cambiado: espera completa', segundos_para_regenerar(ahora, ahora) == 30)
comprobar('a los 10 segundos faltan 20', segundos_para_regenerar(ahora - timedelta(seconds=10), ahora) == 20)
comprobar('pasada la espera se puede', segundos_para_regenerar(ahora - timedelta(seconds=31), ahora) == 0)
comprobar('con fracciones se redondea hacia arriba',
          segundos_para_regenerar(ahora - timedelta(seconds=10, milliseconds=500), ahora) == 20)
comprobar('pin anterior reconocido', pin_fue_anterior('1234', '1111,1234'))
comprobar('pin que nunca fue', not pin_fue_anterior('9999', '1111,1234'))
comprobar('sin historial', not pin_fue_anterior('1234', None))
comprobar('pin vacio', not pin_fue_anterior('', '1234'))
comprobar('agrega al historial', agregar_pin_anterior(None, '1234') == '1234')
comprobar('agrega a continuacion', agregar_pin_anterior('1234', '5678') == '1234,5678')
comprobar('sin repetidos', agregar_pin_anterior('1234,5678', '1234') == '5678,1234')
comprobar('guarda un maximo', agregar_pin_anterior(','.join(f'{n:04d}' for n in range(8)), '9999').split(',')[-1] == '9999'
          and len(agregar_pin_anterior(','.join(f'{n:04d}' for n in range(8)), '9999').split(',')) == 8)

# ---------- texto de cancelacion ----------
texto = texto_motivo_cancelacion('Ana se retiró de la mesa', [(2, 'Hamburguesa'), (1, 'Coca Cola')])
comprobar('motivo con items', texto == 'Cancelada: Ana se retiró de la mesa. Pedido: 2x Hamburguesa, 1x Coca Cola.')
comprobar('motivo sin items', texto_motivo_cancelacion('error', []) == 'Cancelada: error.')
comprobar('motivo recortado a 500', len(texto_motivo_cancelacion('x' * 600, [])) == 500)

print(f'{total - len(fallos)} de {total} chequeos correctos.')
sys.exit(1 if fallos else 0)
