"""Pruebas de restaurante/caja_calculos.py (no necesitan Django, base de datos ni internet).

Uso (desde la raiz del repo):  python Tests/Scripts/probar_caja_calculos.py
"""
import os
import sys
from decimal import Decimal as D

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from restaurante.caja_calculos import (  # noqa: E402
    CajaInvalida, advertencias_de_diferencias, arqueo, arqueo_digital, diferencia, egreso_posible, esperado,
    hay_diferencias, hay_diferencias_caja, total_en_pesos, validar_mercado_pago, validar_moneda, validar_monto,
    validar_montos_por_moneda,
)

total = 0
fallos = []


def comprobar(nombre, condicion):
    global total
    total += 1
    if not condicion:
        fallos.append(nombre)
        print(f'  FALLA: {nombre}')


def rechaza(nombre, funcion, *args, **kwargs):
    try:
        funcion(*args, **kwargs)
    except CajaInvalida:
        comprobar(nombre, True)
    except Exception as error:  # otro tipo de error = falla
        comprobar(f'{nombre} (error inesperado {type(error).__name__}: {error})', False)
    else:
        comprobar(nombre, False)


# ---------- validar_monto ----------
comprobar('acepta entero', validar_monto(100) == D('100.00'))
comprobar('acepta texto', validar_monto('2500.5') == D('2500.50'))
comprobar('acepta Decimal', validar_monto(D('10.25')) == D('10.25'))
comprobar('acepta cero', validar_monto(0) == D('0.00'))
comprobar('float no arrastra error binario', validar_monto(0.1) == D('0.10'))
rechaza('rechaza None', validar_monto, None)
rechaza('rechaza vacio', validar_monto, '  ')
rechaza('rechaza True', validar_monto, True)
rechaza('rechaza texto', validar_monto, 'abc')
rechaza('rechaza NaN', validar_monto, 'NaN')
rechaza('rechaza Infinity', validar_monto, 'Infinity')
rechaza('rechaza negativo', validar_monto, -1)
rechaza('rechaza 3 decimales', validar_monto, '1.005')
rechaza('rechaza enorme', validar_monto, '1e50')
rechaza('rechaza sobre el tope', validar_monto, '100000000000')
comprobar('acepta el tope', validar_monto('99999999999.99') == D('99999999999.99'))
rechaza('positivo=True rechaza cero', validar_monto, 0, 'x', True)
comprobar('positivo=True acepta 0.01', validar_monto('0.01', 'x', True) == D('0.01'))

# ---------- validar_moneda ----------
comprobar('moneda minuscula', validar_moneda(' usd ') == 'USD')
comprobar('moneda ARS', validar_moneda('ARS') == 'ARS')
rechaza('moneda EUR', validar_moneda, 'EUR')
rechaza('moneda vacia', validar_moneda, '')
rechaza('moneda None', validar_moneda, None)

# ---------- validar_montos_por_moneda ----------
r = validar_montos_por_moneda({'ARS': 10000, 'usd': '50'})
comprobar('completa con ceros', r == {'ARS': D('10000.00'), 'USD': D('50.00'), 'BRL': D('0'), 'PYG': D('0')})
comprobar('None = todo cero', validar_montos_por_moneda(None) == {m: D('0') for m in ('ARS', 'USD', 'BRL', 'PYG')})
rechaza('moneda desconocida', validar_montos_por_moneda, {'EUR': 1})
rechaza('no es objeto', validar_montos_por_moneda, [1, 2])
rechaza('moneda repetida', validar_montos_por_moneda, {'USD': 1, 'usd': 2})
rechaza('monto invalido adentro', validar_montos_por_moneda, {'ARS': -5})
rechaza('cierre exige las cuatro', validar_montos_por_moneda, {'ARS': 1, 'USD': 0}, True)
comprobar('cierre con las cuatro', validar_montos_por_moneda({'ARS': 1, 'USD': 0, 'BRL': 0, 'PYG': 0}, True)['ARS'] == D('1.00'))

# ---------- esperado / diferencia ----------
comprobar('esperado', esperado(10000, '500.50', 200) == D('10300.50'))
comprobar('esperado sin movimientos', esperado(0, 0, 0) == D('0.00'))
comprobar('faltante', diferencia(10250, 10300) == D('-50.00'))
comprobar('sobrante', diferencia(10310.25, 10300) == D('10.25'))
comprobar('sin diferencia', diferencia(5, 5) == D('0.00'))

# ---------- arqueo ----------
a = arqueo({'ARS': D('10000'), 'USD': D('50')}, {'ARS': D('500')}, {'ARS': D('200')})
comprobar('arqueo abierto: esperado ARS', a['ARS']['esperado'] == D('10300.00'))
comprobar('arqueo abierto: esperado USD', a['USD']['esperado'] == D('50.00'))
comprobar('arqueo abierto: sin declarado', a['ARS']['declarado'] is None and a['ARS']['diferencia'] is None)
comprobar('arqueo trae las cuatro monedas', list(a) == ['ARS', 'USD', 'BRL', 'PYG'])
comprobar('arqueo BRL vacio', a['BRL']['esperado'] == D('0.00') and a['BRL']['ingresos'] == D('0.00'))
c = arqueo({'ARS': D('10000'), 'USD': D('50')}, {'ARS': D('500')}, {'ARS': D('200')},
           {'ARS': D('10250'), 'USD': D('50'), 'BRL': D('0'), 'PYG': D('0')})
comprobar('arqueo cerrado: diferencia ARS', c['ARS']['diferencia'] == D('-50.00'))
comprobar('arqueo cerrado: USD justo', c['USD']['diferencia'] == D('0.00'))
comprobar('hay diferencias', hay_diferencias(c) is True)
justo = arqueo({'ARS': D('100')}, {}, {}, {'ARS': D('100'), 'USD': D('0'), 'BRL': D('0'), 'PYG': D('0')})
comprobar('no hay diferencias', hay_diferencias(justo) is False)
comprobar('abierta: hay_diferencias False', hay_diferencias(a) is False)
# propina en efectivo = ingreso; vuelto = egreso en pesos
p = arqueo({'ARS': D('1000')}, {'ARS': D('5000')}, {'ARS': D('250.50')})
comprobar('venta con vuelto', p['ARS']['esperado'] == D('5749.50'))

# ---------- egreso_posible ----------
comprobar('egreso igual al esperado', egreso_posible(D('100'), D('100')) is True)
comprobar('egreso menor', egreso_posible(D('100'), D('99.99')) is True)
comprobar('egreso mayor', egreso_posible(D('100'), D('100.01')) is False)

# ---------- Mercado Pago (dinero digital) ----------
d0 = arqueo_digital(D('15000'), D('0'))
comprobar('MP abierta: esperado', d0['esperado'] == D('15000.00') and d0['declarado'] is None and d0['diferencia'] is None)
comprobar('MP siempre en pesos', d0['moneda'] == 'ARS')
d1 = arqueo_digital(D('15000'), D('0'), D('14900'))
comprobar('MP faltante', d1['diferencia'] == D('-100.00'))
comprobar('MP justo', arqueo_digital(D('50.5'), 0, D('50.50'))['diferencia'] == D('0.00'))
comprobar('MP sin cobros', arqueo_digital(None, None)['esperado'] == D('0.00'))
comprobar('MP con egreso', arqueo_digital(D('100'), D('30'))['esperado'] == D('70.00'))

comprobar('MP omitido sin cobros = 0', validar_mercado_pago(None, D('0')) == D('0'))
comprobar('MP vacio sin cobros = 0', validar_mercado_pago('  ', D('0')) == D('0'))
rechaza('MP omitido con cobros registrados', validar_mercado_pago, None, D('15000'))
rechaza('MP negativo', validar_mercado_pago, -1, D('0'))
rechaza('MP con 3 decimales', validar_mercado_pago, '1.001', D('0'))
comprobar('MP informado', validar_mercado_pago('14900.5', D('15000')) == D('14900.50'))
comprobar('MP informado en 0 con cobros (no llego nada)', validar_mercado_pago(0, D('15000')) == D('0.00'))

# total en pesos: efectivo convertido + dinero digital
cot = {'USD': D('1500'), 'BRL': D('280'), 'PYG': D('0.2388')}
t = total_en_pesos({'ARS': D('10300'), 'USD': D('50'), 'BRL': D('0'), 'PYG': D('1000')}, cot, D('15000'))
comprobar('total: efectivo convertido', t['efectivo'] == D('85538.80'))   # 10300 + 75000 + 238.80
comprobar('total: Mercado Pago', t['mercado_pago'] == D('15000.00'))
comprobar('total: suma', t['total'] == D('100538.80'))
comprobar('total: solo pesos no necesita cotizacion', total_en_pesos({'ARS': D('100')}, {})['total'] == D('100.00'))
comprobar('total: moneda con plata sin cotizacion = None', total_en_pesos({'USD': D('5')}, {}) is None)
comprobar('total: moneda en cero sin cotizacion no molesta', total_en_pesos({'ARS': D('5'), 'USD': D('0')}, {})['total'] == D('5.00'))

resumen = {'efectivo': arqueo({'ARS': D('100')}, {}, {}, {'ARS': D('90'), 'USD': D('0'), 'BRL': D('0'), 'PYG': D('0')}),
           'mercado_pago': arqueo_digital(D('500'), 0, D('450'))}
comprobar('hay diferencias en la caja', hay_diferencias_caja(resumen) is True)
avisos = advertencias_de_diferencias(resumen)
comprobar('dos avisos (ARS efectivo y Mercado Pago)', len(avisos) == 2 and 'faltante' in avisos[0] and 'Mercado Pago' in avisos[1])
solo_mp = {'efectivo': arqueo({}, {}, {}, {m: D('0') for m in ('ARS', 'USD', 'BRL', 'PYG')}), 'mercado_pago': arqueo_digital(D('10'), 0, D('12'))}
comprobar('diferencia solo en Mercado Pago cuenta', hay_diferencias_caja(solo_mp) is True)
comprobar('un sobrante dice sobrante', 'sobrante' in advertencias_de_diferencias(solo_mp)[0])
sin = {'efectivo': arqueo({}, {}, {}, {m: D('0') for m in ('ARS', 'USD', 'BRL', 'PYG')}), 'mercado_pago': arqueo_digital(0, 0, 0)}
comprobar('sin diferencias en ningun medio', hay_diferencias_caja(sin) is False and advertencias_de_diferencias(sin) == [])

print(f'\n{total - len(fallos)}/{total} chequeos OK')
sys.exit(1 if fallos else 0)
