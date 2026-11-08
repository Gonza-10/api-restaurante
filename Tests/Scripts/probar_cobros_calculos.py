"""Prueba de los calculos de cobros que no usan la base de datos ni internet: conversion de monedas, redondeo,
equivalentes de la factura, reparto de lo recibido entre cuenta, propina y vuelto, y lectura de la respuesta del BCRA.
Solo libreria estandar; no hace falta tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_cobros_calculos.py
"""
import importlib.util
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / 'restaurante' / 'cobros_calculos.py'
spec = importlib.util.spec_from_file_location('cobros_calculos', RUTA)
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

RESULTADOS = []


def chequear(nombre, obtenido, esperado):
    ok = obtenido == esperado
    RESULTADOS.append(ok)
    print(f"  [{'OK' if ok else 'FALLA'}] {nombre}" + ('' if ok else f'\n         esperado: {esperado!r}\n         obtenido: {obtenido!r}'))


def chequear_error(nombre, funcion, clase, fragmento=''):
    try:
        funcion()
    except clase as error:
        ok = fragmento in str(error)
        RESULTADOS.append(ok)
        print(f"  [{'OK' if ok else 'FALLA'}] {nombre}" + ('' if ok else f'\n         el mensaje era: {error}'))
    except Exception as error:
        RESULTADOS.append(False)
        print(f'  [FALLA] {nombre}\n         lanzo otra cosa: {error!r}')
    else:
        RESULTADOS.append(False)
        print(f'  [FALLA] {nombre}\n         no lanzo ningun error')


print('Conversion y redondeo')
chequear('100 USD a 1450 son 145000 pesos', cc.convertir_a_ars(100, D('1450')), D('145000.00'))
chequear('el guarani vale ~0,2388: 1.000.000 PYG', cc.convertir_a_ars(1000000, D('0.238779')), D('238779.00'))
chequear('mitad hacia arriba (0,005 -> 0,01)', cc.redondear_dinero(D('0.005')), D('0.01'))
chequear('mitad hacia arriba (2,675 -> 2,68, no 2,67 como el float)', cc.redondear_dinero(D('2.675')), D('2.68'))
chequear('un float no arrastra su error binario (0.1 + 0.2)', cc.redondear_dinero(0.1 + 0.2), D('0.30'))
chequear('de pesos a otra moneda: 145000 a 1450', cc.convertir_desde_ars(D('145000'), D('1450')), D('100.00'))
chequear('de pesos a otra moneda redondea: 100000 a 1050', cc.convertir_desde_ars(D('100000'), D('1050')), D('95.24'))
chequear_error('una cotizacion en cero no sirve', lambda: cc.convertir_desde_ars(100, 0), ValueError, 'mayor a cero')
chequear_error('un numero invalido avisa', lambda: cc.redondear_dinero('abc'), ValueError, 'Numero invalido')

print('Equivalentes de la factura (siempre se muestran, incluso si se paga con Mercado Pago)')
cotizaciones = {'USD': D('1000'), 'BRL': D('200'), 'PYG': D('0.2')}
chequear('total 50000 pesos', cc.equivalentes(D('50000'), cotizaciones),
         {'USD': D('50.00'), 'BRL': D('250.00'), 'PYG': D('250000.00')})
chequear('si falta una cotizacion, esa moneda queda en None',
         cc.equivalentes(D('50000'), {'USD': D('1000')}), {'USD': D('50.00'), 'BRL': None, 'PYG': None})
chequear('sin ninguna cotizacion', cc.equivalentes(D('50000'), {}), {'USD': None, 'BRL': None, 'PYG': None})

print('Cobro en efectivo: cuenta, propina y vuelto (todo en pesos)')
chequear('paga justo', cc.calcular_cobro_efectivo(D('10000'), D('10000')),
         {'aplicado': D('10000.00'), 'propina': D('0.00'), 'vuelto': D('0.00')})
chequear('paga de mas: el vuelto es la diferencia', cc.calcular_cobro_efectivo(D('12000'), D('10000')),
         {'aplicado': D('10000.00'), 'propina': D('0.00'), 'vuelto': D('2000.00')})
chequear('con propina: cuenta + propina + vuelto', cc.calcular_cobro_efectivo(D('12000'), D('10000'), propina=D('1000')),
         {'aplicado': D('10000.00'), 'propina': D('1000.00'), 'vuelto': D('1000.00')})
chequear('pago parcial: entrega menos que el saldo y no hay vuelto', cc.calcular_cobro_efectivo(D('4000'), D('10000')),
         {'aplicado': D('4000.00'), 'propina': D('0.00'), 'vuelto': D('0.00')})
chequear('pago parcial con propina: la propina sale de lo recibido', cc.calcular_cobro_efectivo(D('4500'), D('10000'), propina=D('500')),
         {'aplicado': D('4000.00'), 'propina': D('500.00'), 'vuelto': D('0.00')})
chequear('monto de cuenta elegido: paga 3000 con un billete de 5000',
         cc.calcular_cobro_efectivo(D('5000'), D('10000'), monto_cuenta=D('3000')),
         {'aplicado': D('3000.00'), 'propina': D('0.00'), 'vuelto': D('2000.00')})
chequear('solo propina (la cuenta ya esta paga o se paga por otro medio)',
         cc.calcular_cobro_efectivo(D('2000'), D('0'), propina=D('2000')),
         {'aplicado': D('0.00'), 'propina': D('2000.00'), 'vuelto': D('0.00')})
chequear('solo propina con un billete mas grande: el vuelto es en pesos',
         cc.calcular_cobro_efectivo(D('5000'), D('0'), propina=D('2000')),
         {'aplicado': D('0.00'), 'propina': D('2000.00'), 'vuelto': D('3000.00')})
chequear_error('lo recibido no alcanza para el monto elegido',
               lambda: cc.calcular_cobro_efectivo(D('2000'), D('10000'), monto_cuenta=D('3000')), cc.CobroInvalido, 'faltan $1000.00')
chequear_error('la propina no puede superar lo recibido',
               lambda: cc.calcular_cobro_efectivo(D('1000'), D('10000'), propina=D('1500')), cc.CobroInvalido, 'supera lo recibido')
chequear_error('no se puede cobrar mas que el saldo',
               lambda: cc.calcular_cobro_efectivo(D('20000'), D('10000'), monto_cuenta=D('11000')), cc.CobroInvalido, 'supera el saldo')
chequear_error('no se puede cobrar cero', lambda: cc.calcular_cobro_efectivo(D('1000'), D('0')), cc.CobroInvalido, 'nada para cobrar')
chequear_error('recibido en cero', lambda: cc.calcular_cobro_efectivo(0, D('100')), cc.CobroInvalido, 'mayor a cero')
chequear_error('propina negativa', lambda: cc.calcular_cobro_efectivo(D('100'), D('100'), propina=D('-5')), cc.CobroInvalido, 'negativa')

print('Efectivo en otra moneda de punta a punta: 100 USD a 1450, cuenta de 120000, propina de 5000')
recibido = cc.convertir_a_ars(100, D('1450'))
chequear('100 USD equivalen a 145000 pesos', recibido, D('145000.00'))
chequear('se aplican 120000 a la cuenta, 5000 de propina y 20000 de vuelto en pesos',
         cc.calcular_cobro_efectivo(recibido, D('120000'), propina=D('5000')),
         {'aplicado': D('120000.00'), 'propina': D('5000.00'), 'vuelto': D('20000.00')})

print('Respuesta del BCRA (forma esperada, sin verificar contra el BCRA real)')
UN_DIA = {'status': 200, 'results': {'fecha': '2026-11-05', 'detalle': [
    {'codigoMoneda': 'USD', 'descripcion': 'DOLAR E.E.U.U.', 'tipoPase': 1.0, 'tipoCotizacion': 1450.5},
    {'codigoMoneda': 'BRL', 'descripcion': 'REAL', 'tipoPase': 0.18, 'tipoCotizacion': 262.123456789},
    {'codigoMoneda': 'PYG', 'descripcion': 'GUARANI', 'tipoPase': 0.0001, 'tipoCotizacion': 0.238779},
    {'codigoMoneda': 'EUR', 'descripcion': 'EURO', 'tipoPase': 1.1, 'tipoCotizacion': 1600},
]}}
fecha, valores = cc.parsear_cotizaciones_bcra(UN_DIA)
chequear('toma la fecha', fecha, date(2026, 11, 5))
chequear('solo las 3 monedas pedidas (el euro no)', sorted(valores), ['BRL', 'PYG', 'USD'])
chequear('USD', valores['USD'], D('1450.50000000'))
chequear('BRL se redondea a 8 decimales', valores['BRL'], D('262.12345679'))
chequear('PYG', valores['PYG'], D('0.23877900'))

COMO_LISTA = {'results': [
    {'fecha': '2026-11-03', 'detalle': [{'codigoMoneda': 'USD', 'tipoCotizacion': 1400}]},
    {'fecha': '2026-11-05', 'detalle': [{'codigoMoneda': 'USD', 'tipoCotizacion': 1450}]},
    {'fecha': '2026-11-04', 'detalle': [{'codigoMoneda': 'USD', 'tipoCotizacion': 1420}]},
]}
fecha, valores = cc.parsear_cotizaciones_bcra(COMO_LISTA)
chequear('si "results" es una lista, se queda con el dia mas reciente', (fecha, valores), (date(2026, 11, 5), {'USD': D('1450.00000000')}))

chequear('un dia sin datos (fin de semana) devuelve vacio, no error',
         cc.parsear_cotizaciones_bcra({'results': {'fecha': '2026-11-07', 'detalle': []}}), (None, {}))
chequear('detalle ausente tambien es vacio', cc.parsear_cotizaciones_bcra({'results': {'fecha': '2026-11-07'}}), (None, {}))
chequear('valores invalidos se ignoran (cero, texto, negativo, vacio, infinito)', cc.parsear_cotizaciones_bcra({'results': {'fecha': '2026-11-05', 'detalle': [
    {'codigoMoneda': 'USD', 'tipoCotizacion': 0},
    {'codigoMoneda': 'BRL', 'tipoCotizacion': 'abc'},
    {'codigoMoneda': 'PYG', 'tipoCotizacion': -3},
    {'codigoMoneda': 'USD', 'tipoCotizacion': None},
    {'codigoMoneda': 'BRL', 'tipoCotizacion': 'Infinity'},
]}}), (None, {}))
chequear('el codigo de moneda en minuscula tambien se reconoce', cc.parsear_cotizaciones_bcra(
    {'results': {'fecha': '2026-11-05', 'detalle': [{'codigoMoneda': ' usd ', 'tipoCotizacion': '1450'}]}}),
    (date(2026, 11, 5), {'USD': D('1450.00000000')}))
chequear_error('una respuesta sin "results" es invalida', lambda: cc.parsear_cotizaciones_bcra({'status': 500}), cc.RespuestaBcraInvalida)
chequear_error('una respuesta que no es un objeto es invalida', lambda: cc.parsear_cotizaciones_bcra([1, 2]), cc.RespuestaBcraInvalida)
chequear_error('"detalle" que no es lista es invalido',
               lambda: cc.parsear_cotizaciones_bcra({'results': {'detalle': 'x'}}), cc.RespuestaBcraInvalida)

print('Cuando se guarda una cotizacion nueva y cuando no')
chequear('la primera siempre se guarda', cc.necesita_guardar(None, D('1450')), True)
chequear('mismo valor: no se guarda', cc.necesita_guardar(D('1450.00000000'), D('1450')), False)
chequear('valor distinto: se guarda', cc.necesita_guardar(D('1450'), D('1451')), True)

print('Fechas a consultar y estado desactualizado')
fechas = cc.fechas_a_consultar(date(2026, 11, 8))  # domingo
chequear('empieza hoy y retrocede de a un dia', fechas[:3], [date(2026, 11, 8), date(2026, 11, 7), date(2026, 11, 6)])
chequear('son 8 dias', len(fechas), 8)
ahora = datetime(2026, 11, 6, 12, 0)
chequear('nunca consultada: desactualizada', cc.esta_desactualizada(None, ahora), True)
chequear('hace 30 minutos: vigente', cc.esta_desactualizada(ahora - timedelta(minutes=30), ahora), False)
chequear('hace 2 horas justas: todavia vigente', cc.esta_desactualizada(ahora - timedelta(minutes=120), ahora), False)
chequear('hace mas de 2 horas: desactualizada', cc.esta_desactualizada(ahora - timedelta(minutes=121), ahora), True)

print()
print(f'{sum(RESULTADOS)} de {len(RESULTADOS)} chequeos correctos.')
sys.exit(0 if all(RESULTADOS) else 1)
