"""Pruebas de restaurante/cuenta_calculos.py (no necesitan Django, base de datos ni internet).

Uso (desde la raiz del repo):  python Tests/Scripts/probar_cuenta_calculos.py
"""
import os
import sys
from decimal import Decimal as D

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from restaurante.cuenta_calculos import (  # noqa: E402
    SIN_ASIGNAR, descripcion_de_renglon, desglose_por_comensal, equivalentes_para_factura, partes_de_ingreso,
    repartir_en_partes, saldo_de_la_cuenta, total_aprobado,
)

total = 0
fallos = []


def comprobar(nombre, condicion):
    global total
    total += 1
    if not condicion:
        fallos.append(nombre)
        print(f'  FALLA: {nombre}')


# ---------- repartir_en_partes ----------
comprobar('100 / 3 = 33.34 + 33.33 + 33.33', repartir_en_partes('100.00', 3) == [D('33.34'), D('33.33'), D('33.33')])
comprobar('la suma es exacta', sum(repartir_en_partes('100.00', 3)) == D('100.00'))
comprobar('una sola parte', repartir_en_partes('55.55', 1) == [D('55.55')])
comprobar('reparto parejo', repartir_en_partes('90', 3) == [D('30.00')] * 3)
comprobar('0.01 entre 3: un centavo al primero', repartir_en_partes('0.01', 3) == [D('0.01'), D('0.00'), D('0.00')])
for monto, n in [('1234.57', 4), ('0.10', 7), ('99999.99', 13), ('5.00', 2)]:
    comprobar(f'{monto} en {n}: suma exacta', sum(repartir_en_partes(monto, n)) == D(monto))
try:
    repartir_en_partes('10', 0)
    comprobar('cero partes falla', False)
except ValueError:
    comprobar('cero partes falla', True)

# ---------- desglose_por_comensal ----------
renglones = [
    {'sub_total': D('3000.00'), 'comensal': 'Ana'},
    {'sub_total': D('1000.00'), 'comensal': 'Beto'},
    {'sub_total': D('900.00'), 'comensal': 'Ana', 'compartido': ['Ana', 'Beto', 'Usuario no registrado 1']},
    {'sub_total': D('500.00')},
    {'sub_total': D('250.00'), 'comensal': '  '},
]
d = desglose_por_comensal(renglones)
comprobar('Ana: 3000 + 300 compartido', d['Ana'] == D('3300.00'))
comprobar('Beto: 1000 + 300 compartido', d['Beto'] == D('1300.00'))
comprobar('no registrado: 300', d['Usuario no registrado 1'] == D('300.00'))
comprobar('lo sin comensal queda sin asignar', d[SIN_ASIGNAR] == D('750.00'))
comprobar('el desglose suma el total', sum(d.values()) == D('5650.00'))
comprobar('orden de aparicion', list(d) == ['Ana', 'Beto', 'Usuario no registrado 1', SIN_ASIGNAR])
d2 = desglose_por_comensal([{'sub_total': D('100.00'), 'compartido': ['A', 'B', 'C']}])
comprobar('reparto de centavos en el desglose', d2 == {'A': D('33.34'), 'B': D('33.33'), 'C': D('33.33')})
d3 = desglose_por_comensal([{'sub_total': D('10'), 'compartido': ['A', 'A', ' A ']}])
comprobar('un participante repetido cuenta una vez', d3 == {'A': D('10.00')})
comprobar('sin renglones', desglose_por_comensal([]) == {})
d4 = desglose_por_comensal([{'sub_total': D('10'), 'comensal': 'Ana', 'compartido': []}])
comprobar('compartido vacio = del comensal', d4 == {'Ana': D('10.00')})

# ---------- saldo ----------
pagos = [
    {'estado': 'Aprobado', 'monto': D('3000')},
    {'estado': 'Pendiente', 'monto': D('1500.50')},
    {'estado': 'Rechazado', 'monto': D('9999')},
    {'estado': 'Cancelado', 'monto': D('9999')},
    {'estado': 'Expirado', 'monto': D('9999')},
    {'estado': 'Anulado', 'monto': D('9999')},
]
comprobar('saldo = total - aprobado - pendiente', saldo_de_la_cuenta(D('10000'), pagos) == D('5499.50'))
comprobar('saldo sin pagos', saldo_de_la_cuenta(D('10000'), []) == D('10000.00'))
comprobar('saldo cero cuando esta pagada', saldo_de_la_cuenta(D('100'), [{'estado': 'Aprobado', 'monto': D('100')}]) == D('0.00'))
comprobar('anulado libera el saldo', saldo_de_la_cuenta(D('100'), [{'estado': 'Anulado', 'monto': D('100')}]) == D('100.00'))
comprobar('total aprobado', total_aprobado(pagos) == D('3000.00'))

# ---------- partes_de_ingreso (como se anota en la caja) ----------
comprobar('sin propina: todo venta', partes_de_ingreso(D('10000'), D('0'), D('1'), 'ARS') == (D('10000.00'), D('0')))
comprobar('pesos con propina', partes_de_ingreso(D('11000'), D('1000'), D('1'), 'ARS') == (D('10000.00'), D('1000.00')))
v, p = partes_de_ingreso(D('50'), D('1500'), D('1500'), 'USD')
comprobar('USD: propina de 1500 pesos = 1 USD', (v, p) == (D('49.00'), D('1.00')))
v, p = partes_de_ingreso(D('1000'), D('0.50'), D('0.2388'), 'PYG')
comprobar('PYG: la suma es lo recibido', v + p == D('1000.00'))
v, p = partes_de_ingreso(D('2'), D('9999'), D('1500'), 'USD')
comprobar('la propina no supera lo recibido', p == D('2.00') and v == D('0.00'))
comprobar('suma exacta siempre', all(sum(partes_de_ingreso(D(r), D(pr), D(c), m)) == D(r)
                                      for r, pr, c, m in [('100', '333.33', '1450', 'USD'), ('7', '10', '280.123', 'BRL'), ('5000', '0', '1', 'ARS')]))

# ---------- equivalentes / descripcion ----------
e = equivalentes_para_factura(D('145000'), {'USD': D('1450'), 'PYG': D('0.2388')})
comprobar('equivalente USD', e['USD'] == D('100.00'))
comprobar('equivalente BRL sin cotizacion = None', e['BRL'] is None)
comprobar('descripcion sin quitados', descripcion_de_renglon('Hamburguesa', []) == 'Hamburguesa')
comprobar('descripcion con quitados', descripcion_de_renglon('Hamburguesa', ['Cebolla', 'Tomate']) == 'Hamburguesa (sin Cebolla, Tomate)')
comprobar('descripcion larga se corta', len(descripcion_de_renglon('x' * 300, ['y'])) == 150)
comprobar('descripcion con extras', descripcion_de_renglon('Hamburguesa', [], ['Cheddar x2', 'Aderezo']) == 'Hamburguesa (con Cheddar x2, Aderezo)')
comprobar('descripcion con quitados y extras', descripcion_de_renglon('Hamburguesa', ['Cebolla'], ['Cheddar']) == 'Hamburguesa (sin Cebolla; con Cheddar)')
comprobar('descripcion sin extras igual que antes', descripcion_de_renglon('Hamburguesa', ['Cebolla'], []) == 'Hamburguesa (sin Cebolla)')
comprobar('descripcion larga con extras se corta', len(descripcion_de_renglon('x' * 140, ['y'], ['z' * 50])) == 150)

print(f'\n{total - len(fallos)}/{total} chequeos OK')
sys.exit(1 if fallos else 0)
