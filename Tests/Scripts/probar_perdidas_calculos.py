"""Prueba de los calculos de perdidas que no usan la base de datos (motivos, valor a costo real de lote, resumen).
Solo libreria estandar; no hace falta tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_perdidas_calculos.py
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


print('Lista cerrada de motivos')
chequear('son 6 y el orden es fijo', list(sc.CODIGOS_MOTIVO),
         ['vencimiento', 'rotura_derrame', 'error_cocina', 'devolucion_cliente', 'consumo_personal', 'otro'])
chequear('todos tienen etiqueta', all(sc.ETIQUETA_MOTIVO[c] for c in sc.CODIGOS_MOTIVO), True)
chequear('los codigos no se repiten', len(set(sc.CODIGOS_MOTIVO)), len(sc.CODIGOS_MOTIVO))
chequear('solo "otro" pide nota (constante)', sc.MOTIVO_OTRO, 'otro')

print('Valor de una perdida: costo REAL de cada lote, no un promedio')
# 300 g salieron de un lote viejo a 0.002 y 200 g de uno nuevo a 0.004 (FEFO): 0.6 + 0.8
chequear('dos lotes con costos distintos', sc.valorizar_tomas([(D('-300'), D('0.002')), (D('-200'), D('0.004'))]),
         (D('1.40'), True))
chequear('no es el promedio de los costos (500 g x 0.003 daria 1.50)',
         sc.valorizar_tomas([(D('300'), D('0.002')), (D('200'), D('0.004'))])[0] != D('1.50'), True)
chequear('acepta cantidades con signo (el libro las guarda negativas)',
         sc.valorizar_tomas([(D('-2'), D('150'))]), (D('300.00'), True))
chequear('un lote sin costo deja el valor incompleto', sc.valorizar_tomas([(D('-100'), D('0'))]), (D('0.00'), False))
chequear('incompleto aunque otro lote si tenga costo',
         sc.valorizar_tomas([(D('-100'), D('0')), (D('-1'), D('50'))]), (D('50.00'), False))
chequear('sin tomas', sc.valorizar_tomas([]), (D('0.00'), True))
chequear('redondea al final, no en cada tramo', sc.valorizar_tomas([(D('1'), D('0.004')), (D('1'), D('0.004')), (D('1'), D('0.004'))]),
         (D('0.01'), True))

print('Resumen de perdidas (Admin y Gerente)')
filas = [
    {'tipo': 'insumo', 'id': 1, 'nombre': 'Harina', 'motivo': 'vencimiento', 'valor': D('300.00'), 'completo': True},
    {'tipo': 'plato', 'id': 10, 'nombre': 'Pizza', 'motivo': 'error_cocina', 'valor': D('500.00'), 'completo': True},
    {'tipo': 'plato', 'id': 10, 'nombre': 'Pizza', 'motivo': 'error_cocina', 'valor': D('500.00'), 'completo': True},
    {'tipo': 'insumo', 'id': 2, 'nombre': 'Huevo', 'motivo': 'rotura_derrame', 'valor': D('200.00'), 'completo': True},
]
r = sc.resumen_perdidas(filas)
chequear('cantidad de registros', r['registros'], 4)
chequear('valor total', r['valor_total'], D('1500.00'))
chequear('motivos de mayor a menor valor', [m['motivo'] for m in r['por_motivo']], ['error_cocina', 'vencimiento', 'rotura_derrame'])
chequear('error de cocina: 2 registros y 1000', (r['por_motivo'][0]['registros'], r['por_motivo'][0]['valor']), (2, D('1000.00')))
chequear('porcentaje del valor perdido por motivo', [m['porcentaje'] for m in r['por_motivo']], [66.7, 20.0, 13.3])
chequear('reparto insumo/plato', (r['por_tipo']['insumo'], r['por_tipo']['plato']),
         ({'registros': 2, 'valor': D('500.00')}, {'registros': 2, 'valor': D('1000.00')}))
chequear('el item que mas pierde es la pizza', (r['items_que_mas_pierden'][0]['nombre'], r['items_que_mas_pierden'][0]['registros'],
         r['items_que_mas_pierden'][0]['valor']), ('Pizza', 2, D('1000.00')))
chequear('un insumo y un plato con el mismo id no se mezclan',
         len(sc.resumen_perdidas([
             {'tipo': 'insumo', 'id': 1, 'nombre': 'Harina', 'motivo': 'otro', 'valor': D('1'), 'completo': True},
             {'tipo': 'plato', 'id': 1, 'nombre': 'Pizza', 'motivo': 'otro', 'valor': D('1'), 'completo': True},
         ])['items_que_mas_pierden']), 2)
chequear('limite de items', len(sc.resumen_perdidas(filas, limite_items=1)['items_que_mas_pierden']), 1)
chequear('valor completo si todas lo son', r['valor_completo'], True)
chequear('valor incompleto si alguna no lo es',
         sc.resumen_perdidas([{**filas[0], 'completo': False}])['valor_completo'], False)
vacio = sc.resumen_perdidas([])
chequear('sin perdidas: todo en cero', (vacio['registros'], vacio['valor_total'], vacio['por_motivo']), (0, D('0.00'), []))
chequear('con valor cero el porcentaje no se calcula (no se divide por cero)',
         sc.resumen_perdidas([{**filas[0], 'valor': D('0')}])['por_motivo'][0]['porcentaje'], None)
chequear('a igual valor, ordena por etiqueta',
         [m['motivo'] for m in sc.resumen_perdidas([
             {'tipo': 'insumo', 'id': 1, 'nombre': 'A', 'motivo': 'vencimiento', 'valor': D('5'), 'completo': True},
             {'tipo': 'insumo', 'id': 2, 'nombre': 'B', 'motivo': 'error_cocina', 'valor': D('5'), 'completo': True},
         ])['por_motivo']], ['error_cocina', 'vencimiento'])

ok = sum(RESULTADOS)
print(f'\nResultado: {ok}/{len(RESULTADOS)} correctas')
sys.exit(0 if ok == len(RESULTADOS) else 1)
