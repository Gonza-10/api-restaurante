"""Prueba de los calculos del stock que no usan la base de datos (reparto FEFO, costos, semaforo, textos).
Solo libreria estandar; no hace falta tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_stock_calculos.py
"""
import importlib.util
import sys
from decimal import Decimal as D
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / 'restaurante' / 'stock_calculos.py'
spec = importlib.util.spec_from_file_location('stock_calculos', RUTA)
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

RESULTADOS = []


def chequear(nombre, obtenido, esperado):
    ok = obtenido == esperado
    RESULTADOS.append(ok)
    print(f"  [{'OK' if ok else 'FALLA'}] {nombre}" + ('' if ok else f'\n         esperado: {esperado!r}\n         obtenido: {obtenido!r}'))


print('Costo por unidad base')
chequear('160000 pagados por 80000 g = 2 por g', sc.costo_unitario('160000', '80000'), D('2.000000'))
chequear('100 por 3 unidades = 33.333333 (6 decimales)', sc.costo_unitario('100', '3'), D('33.333333'))
chequear('costo total de un lote', sc.costo_total_lote('150000', '0.002'), D('300.00'))

print('Reparto FEFO entre lotes (ya ordenados por vencimiento)')
lotes = [(1, D('100')), (2, D('50')), (3, D('70'))]
chequear('120 = 100 del primero + 20 del segundo', sc.repartir_fefo(lotes, D('120')), ([(1, D('100')), (2, D('20'))], D('0')))
chequear('exacto: 220 = todo', sc.repartir_fefo(lotes, D('220'))[1], D('0'))
chequear('pide mas de lo que hay: informa el faltante', sc.repartir_fefo([(1, D('100'))], D('130')), ([(1, D('100'))], D('30')))
chequear('sin lotes: todo es faltante', sc.repartir_fefo([], D('5')), ([], D('5')))
chequear('salta lotes vacios', sc.repartir_fefo([(1, D('0')), (2, D('5'))], D('5'))[0], [(2, D('5'))])

print('Textos de cantidad')
chequear('150000 g = 150 kg', sc.texto_cantidad(D('150000.000'), 'Masa'), '150 kg')
chequear('2500 ml = 2.5 l', sc.texto_cantidad(D('2500'), 'Volumen'), '2.5 l')
chequear('250 g sigue en g', sc.texto_cantidad(D('250'), 'Masa'), '250 g')
chequear('12 unidades', sc.texto_cantidad(D('12'), 'Unidad'), '12 u')
chequear('cero', sc.texto_cantidad(D('0'), 'Masa'), '0 g')
chequear('3.000 es entero', sc.es_entera('3.000'), True)
chequear('2.5 no es entero', sc.es_entera('2.5'), False)

print('Gravedad: lo peor primero, sin promediar')
filas = [('Ok', D('90'), 'Sal'), ('Critico', D('10'), 'Carne'), ('Bajo', D('40'), 'Harina'),
         ('Agotado', D('0'), 'Queso'), ('Critico', D('5'), 'Aceite'), ('SinObjetivo', None, 'Hielo')]
orden = [f[2] for f in sorted(filas, key=lambda f: sc.clave_gravedad(*f))]
chequear('orden de gravedad', orden, ['Queso', 'Aceite', 'Carne', 'Harina', 'Hielo', 'Sal'])
resumen = sc.resumen_estados([f[0] for f in filas])
chequear('el peor estado manda', (resumen['peor_estado'], resumen['semaforo_general']), ('Agotado', 'rojo'))
chequear('requieren atencion = agotado + critico + bajo', resumen['requieren_atencion'], 4)
chequear('no hay promedio en el resumen', 'promedio' in resumen or 'porcentaje' in resumen, False)
chequear('todo en verde', sc.resumen_estados(['Ok', 'Ok'])['semaforo_general'], 'verde')
chequear('sin insumos', sc.resumen_estados([])['peor_estado'], None)

ok = sum(RESULTADOS)
print(f'\nResultado: {ok}/{len(RESULTADOS)} correctas')
sys.exit(0 if ok == len(RESULTADOS) else 1)
