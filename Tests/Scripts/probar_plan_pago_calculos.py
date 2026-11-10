"""Pruebas del plan de pago y del identificador de dispositivo (restaurante/plan_pago_calculos.py). No necesitan Django, base de datos ni internet.

Uso (desde la raiz del repo):  python Tests/Scripts/probar_plan_pago_calculos.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from restaurante.plan_pago_calculos import (  # noqa: E402
    MAX_PARTES, PlanInvalido, partes_al_aire, resumen_texto, validar_dispositivo, validar_plan,
)

total = 0
fallos = []


def comprobar(nombre, condicion):
    global total
    total += 1
    if not condicion:
        fallos.append(nombre)
        print(f'  FALLA: {nombre}')


def falla(nombre, funcion, *args):
    try:
        funcion(*args)
    except PlanInvalido:
        comprobar(nombre, True)
    else:
        comprobar(nombre, False)


# ---------- dispositivo ----------
comprobar('dispositivo valido', validar_dispositivo('abc12345') == 'abc12345')
comprobar('dispositivo con guiones y espacios alrededor', validar_dispositivo('  d-1234_abcd ') == 'd-1234_abcd')
falla('dispositivo corto', validar_dispositivo, 'abc')
falla('dispositivo con simbolos', validar_dispositivo, 'abc 12345!')
falla('dispositivo largo', validar_dispositivo, 'a' * 65)
falla('dispositivo vacio', validar_dispositivo, None)
falla('dispositivo numerico', validar_dispositivo, 12345678)

# ---------- plan ----------
plan = validar_plan('todo', [{'metodo': 'efectivo', 'monto': 20000}])
comprobar('un solo medio', plan == {'modo': 'todo', 'partes': [{'metodo': 'Efectivo', 'monto': '20000.00', 'propina': '0.00'}]})
plan = validar_plan(None, [{'metodo': 'Mercado Pago', 'monto': '8000.50', 'propina': 800}])
comprobar('modo vacio es todo y mercado pago con espacio', plan['modo'] == 'todo' and plan['partes'][0]['metodo'] == 'MercadoPago')
comprobar('propina normalizada', plan['partes'][0]['propina'] == '800.00' and plan['partes'][0]['monto'] == '8000.50')
combinado = validar_plan('consumo', [
    {'metodo': 'efectivo', 'monto': 15000, 'propina': 1500},
    {'metodo': 'tarjeta', 'monto': 5000},
    {'metodo': 'mercadopago', 'monto': 8000, 'propina': 800},
])
comprobar('combinado conserva el orden', [p['metodo'] for p in combinado['partes']] == ['Efectivo', 'Tarjeta', 'MercadoPago'])
comprobar('modo consumo', combinado['modo'] == 'consumo')
comprobar('al aire: efectivo y tarjeta', [p['metodo'] for p in partes_al_aire(combinado)] == ['Efectivo', 'Tarjeta'])
comprobar('al aire con solo mercado pago', partes_al_aire(validar_plan('todo', [{'metodo': 'mercadopago', 'monto': 1}])) == [])
comprobar('al aire sin plan', partes_al_aire(None) == [])
comprobar('resumen', resumen_texto(combinado) == 'Efectivo $15000.00 + Tarjeta $5000.00 + Mercado Pago $8000.00')
comprobar('resumen sin plan', resumen_texto(None) == '')
comprobar('partes iguales valido', validar_plan('partes_iguales', [{'metodo': 'tarjeta', 'monto': 100}])['modo'] == 'partes_iguales')

falla('modo desconocido', validar_plan, 'mitad', [{'metodo': 'efectivo', 'monto': 1}])
falla('sin partes', validar_plan, 'todo', [])
falla('partes no es lista', validar_plan, 'todo', {'metodo': 'efectivo', 'monto': 1})
falla('medio desconocido', validar_plan, 'todo', [{'metodo': 'transferencia', 'monto': 1}])
falla('medio repetido', validar_plan, 'todo', [{'metodo': 'efectivo', 'monto': 1}, {'metodo': 'Efectivo', 'monto': 2}])
falla('monto cero', validar_plan, 'todo', [{'metodo': 'efectivo', 'monto': 0}])
falla('monto negativo', validar_plan, 'todo', [{'metodo': 'efectivo', 'monto': -5}])
falla('monto no numerico', validar_plan, 'todo', [{'metodo': 'efectivo', 'monto': 'mucho'}])
falla('propina negativa', validar_plan, 'todo', [{'metodo': 'efectivo', 'monto': 5, 'propina': -1}])
falla('parte que no es objeto', validar_plan, 'todo', ['efectivo'])
falla('demasiadas partes', validar_plan, 'todo', [{'metodo': 'efectivo', 'monto': 1}] * (MAX_PARTES + 1))

print(f'{total - len(fallos)}/{total} pruebas correctas')
sys.exit(1 if fallos else 0)
