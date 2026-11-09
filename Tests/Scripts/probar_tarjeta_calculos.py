"""Pruebas del pago con tarjeta (restaurante/cobros_calculos.py). No necesitan Django, base de datos ni internet.

Uso (desde la raiz del repo):  python Tests/Scripts/probar_tarjeta_calculos.py
"""
import os
import sys
from decimal import Decimal as D

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from restaurante.cobros_calculos import CobroInvalido, calcular_cobro_tarjeta, metodo_pago_solicitado  # noqa: E402
from restaurante.comprobante_calculos import MEDIOS  # noqa: E402

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
    except CobroInvalido:
        comprobar(nombre, True)
    else:
        comprobar(nombre, False)


# ---------- medio que elige el cliente al pedir la cuenta ----------
comprobar('efectivo', metodo_pago_solicitado('efectivo') == 'Efectivo')
comprobar('tarjeta', metodo_pago_solicitado('tarjeta') == 'Tarjeta')
comprobar('mercadopago', metodo_pago_solicitado('mercadopago') == 'MercadoPago')
comprobar('mayusculas y espacios', metodo_pago_solicitado('  TARJETA ') == 'Tarjeta')
comprobar('"Mercado Pago" con espacio', metodo_pago_solicitado('Mercado Pago') == 'MercadoPago')
comprobar('"mercado_pago" con guion bajo', metodo_pago_solicitado('mercado_pago') == 'MercadoPago')
comprobar('"transferencia" (lo manda el front viejo) se ignora', metodo_pago_solicitado('transferencia') is None)
comprobar('"ninguno" (cuenta sin consumos) se ignora', metodo_pago_solicitado('ninguno') is None)
comprobar('vacio se ignora', metodo_pago_solicitado('') is None)
comprobar('None se ignora', metodo_pago_solicitado(None) is None)
comprobar('un numero se ignora', metodo_pago_solicitado(5) is None)
comprobar('una lista se ignora', metodo_pago_solicitado(['tarjeta']) is None)

# ---------- cuanto cubre un cobro con tarjeta ----------
comprobar('sin monto: se cobra todo el saldo', calcular_cobro_tarjeta(D('15000.00')) == D('15000.00'))
comprobar('pago parcial', calcular_cobro_tarjeta(D('15000.00'), D('6000')) == D('6000.00'))
comprobar('pago exacto del saldo', calcular_cobro_tarjeta(D('15000.00'), D('15000.00')) == D('15000.00'))
comprobar('redondea a centavos', calcular_cobro_tarjeta(D('100'), D('33.333')) == D('33.33'))
comprobar('acepta el monto como texto', calcular_cobro_tarjeta('1000.50', '250.25') == D('250.25'))
falla('el monto no puede superar el saldo', calcular_cobro_tarjeta, D('15000'), D('15000.01'))
falla('monto cero', calcular_cobro_tarjeta, D('15000'), D('0'))
falla('monto negativo', calcular_cobro_tarjeta, D('15000'), D('-5'))
falla('cuenta sin saldo', calcular_cobro_tarjeta, D('0'))
falla('cuenta sin saldo, aunque se indique monto', calcular_cobro_tarjeta, D('0'), D('100'))
falla('saldo negativo', calcular_cobro_tarjeta, D('-1'))

# ---------- comprobante ----------
comprobar('el comprobante nombra el medio Tarjeta', MEDIOS.get('Tarjeta') == 'Tarjeta')
comprobar('y no pierde los otros medios', MEDIOS['Efectivo'] == 'Efectivo' and MEDIOS['MercadoPago'] == 'Mercado Pago')

print(f'\n{total - len(fallos)} de {total} chequeos correctos.')
if fallos:
    print('FALLARON:', ', '.join(fallos))
    sys.exit(1)
