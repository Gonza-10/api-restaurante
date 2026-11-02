"""Prueba de los calculos del hito 6 que no usan la base de datos: ciclos entre elaboraciones, cuanto se necesita y cuanto
sale al elaborar, costo real del lote producido, vencimientos y lista de reposicion. Solo libreria estandar; no hace falta
tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_elaboraciones_calculos.py
"""
import importlib.util
import sys
from datetime import date
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


# insumos: 1 tomate (g) 2 cebolla (g) 3 aceite (ml) 4 huevo (u) 5 harina (g)
# elaboraciones: 10 = salsa base (con 1, 2, 3); 11 = salsa picante (con 10 y 3); 12 = masa (con 5 y 4)
print('Ciclos entre elaboraciones')
GRAFO = {10: [1, 2, 3], 11: [10, 3], 12: [5, 4]}
chequear('sin ciclo: una elaboracion nueva con insumos comunes', sc.hay_ciclo(GRAFO, 13, [1, 5]), False)
chequear('una elaboracion puede usar otra (un nivel)', sc.hay_ciclo(GRAFO, 13, [10]), False)
chequear('y otra que usa otra (dos niveles)', sc.hay_ciclo(GRAFO, 13, [11, 12]), False)
chequear('no puede usarse a si misma', sc.hay_ciclo(GRAFO, 10, [10, 1]), True)
chequear('ciclo directo: la salsa base usa la picante, que usa la base', sc.hay_ciclo(GRAFO, 10, [11]), True)
chequear('ciclo indirecto de tres: 12 usa 13, 13 usa 11, 11 usa 12', sc.hay_ciclo({13: [11], 11: [12]}, 12, [13]), True)
chequear('ya hay un vinculo pero no cierra el ciclo', sc.hay_ciclo({13: [11], 11: [10]}, 12, [13]), False)
chequear('el mismo ingrediente por dos caminos no es ciclo (rombo)', sc.hay_ciclo({20: [1], 21: [1], 22: [20, 21]}, 23, [22]), False)

print('Cuanto se necesita y cuanto sale al elaborar')
SALSA = [(1, D('800'), 'Masa', 'Tomate'), (2, D('150'), 'Masa', 'Cebolla'), (3, D('50'), 'Volumen', 'Aceite')]
c = sc.calcular_produccion(SALSA, D('1000'), D('1'), 'Masa')
chequear('una tanda', (c['cantidad'], c['necesario'], c['errores']),
         (D('1000'), [(1, D('800')), (2, D('150')), (3, D('50'))], []))
c = sc.calcular_produccion(SALSA, D('1000'), D('2.5'), 'Masa')
chequear('2,5 tandas', (c['cantidad'], c['necesario']), (D('2500'), [(1, D('2000')), (2, D('375')), (3, D('125'))]))
c = sc.calcular_produccion(list(reversed(SALSA)), D('1000'), D('1'), 'Masa')
chequear('los ingredientes salen ordenados por id (siempre el mismo orden)', [i for i, _ in c['necesario']], [1, 2, 3])
MASA = [(5, D('500'), 'Masa', 'Harina'), (4, D('2'), 'Unidad', 'Huevo')]
c = sc.calcular_produccion(MASA, D('10'), D('3'), 'Unidad')
chequear('3 tandas de masa: 6 huevos, salen 30 unidades', (c['cantidad'], c['necesario'], c['errores']),
         (D('30'), [(4, D('6')), (5, D('1500'))], []))
c = sc.calcular_produccion([(4, D('3'), 'Unidad', 'Huevo'), (5, D('500'), 'Masa', 'Harina')], D('10'), D('0.5'), 'Unidad')
chequear('media tanda con 3 huevos daria 1,5 huevos: error', [e['campo'] for e in c['errores']], ['tandas'])
chequear('el mensaje nombra el insumo', 'Huevo' in c['errores'][0]['mensaje'], True)
c = sc.calcular_produccion(SALSA, D('3'), D('0.5'), 'Unidad')
chequear('si lo producido se cuenta en unidades y sale una fraccion: error', len(c['errores']), 1)
c = sc.calcular_produccion(SALSA, D('1000'), D('0.5'), 'Masa')
chequear('en gramos o mililitros las fracciones estan bien', c['errores'], [])

print('Costo real del lote producido (no es un promedio)')
costo, completo = sc.costo_unitario_producido([(D('-800'), D('0.005')), (D('-150'), D('0.002')), (D('-50'), D('0.010'))], D('1000'))
# 800*0.005 = 4 ; 150*0.002 = 0.30 ; 50*0.01 = 0.50 -> 4.80 / 1000
chequear('4,80 de insumos sobre 1000 g', (costo, completo), (D('0.004800'), True))
costo, completo = sc.costo_unitario_producido([(D('-100'), D('2')), (D('-100'), D('4'))], D('50'))
chequear('dos lotes de distinto costo: se paga cada uno al suyo', (costo, completo), (D('12.000000'), True))
costo, completo = sc.costo_unitario_producido([(D('-100'), D('2')), (D('-100'), D('0'))], D('50'))
chequear('un lote sin costo: queda incompleto', (costo, completo), (D('4.000000'), False))
costo, completo = sc.costo_unitario_producido([(D('-100'), D('0'))], D('50'))
chequear('todo sin costo: cero e incompleto', (costo, completo), (D('0'), False))

print('Vencimientos')
HOY = date(2026, 11, 2)
chequear('dias que faltan', sc.dias_restantes(date(2026, 11, 7), HOY), 5)
chequear('vence hoy: 0 dias', sc.dias_restantes(HOY, HOY), 0)
chequear('ya vencio: negativo', sc.dias_restantes(date(2026, 10, 31), HOY), -2)
chequear('faltan 6 dias con aviso de 5: todavia no', sc.estado_vencimiento(6, 5), None)
chequear('faltan 5 con aviso de 5: por vencer', sc.estado_vencimiento(5, 5), 'por_vencer')
chequear('vence hoy: por vencer (se usa hasta hoy inclusive)', sc.estado_vencimiento(0, 5), 'por_vencer')
chequear('ayer: vencido', sc.estado_vencimiento(-1, 5), 'vencido')
chequear('aviso de 0 dias: solo avisa el mismo dia', (sc.estado_vencimiento(0, 0), sc.estado_vencimiento(1, 0)), ('por_vencer', None))
chequear('textos', [sc.texto_dias_vencimiento(d) for d in (3, 1, 0, -1, -4)],
         ['vence en 3 dias', 'vence manana', 'vence hoy', 'vencio ayer', 'vencio hace 4 dias'])
filas = [
    {'dias_restantes': 3, 'insumo_nombre': 'Leche', 'lote': 7},
    {'dias_restantes': 1, 'insumo_nombre': 'Crema', 'lote': 9},
    {'dias_restantes': 1, 'insumo_nombre': 'Brioche', 'lote': 4},
    {'dias_restantes': -2, 'insumo_nombre': 'Yogur', 'lote': 2},
]
chequear('orden: el que vence antes primero, y a igual dia por nombre',
         [f['lote'] for f in sorted(filas, key=sc.clave_vencimiento)], [2, 4, 9, 7])

print('Lista de reposicion')
chequear('lo que falta para llegar al objetivo', sc.faltante_a_objetivo(D('300'), D('1000')), D('700'))
chequear('si ya llego, no falta nada', sc.faltante_a_objetivo(D('1200'), D('1000')), D('0'))
chequear('tandas: se redondea hacia arriba', (sc.tandas_para(D('700'), D('1000')), sc.tandas_para(D('1000'), D('1000')),
                                              sc.tandas_para(D('1001'), D('1000'))), (1, 1, 2))
chequear('entra si esta agotado, critico o bajo', [sc.entra_en_reposicion(e, D('1'), D('10')) for e in ('Agotado', 'Critico', 'Bajo', 'Ok')],
         [True, True, True, False])
chequear('sin objetivo nunca entra', sc.entra_en_reposicion('Agotado', D('0'), D('0')), False)
chequear('con todos=True entra cualquiera por debajo del objetivo', (sc.entra_en_reposicion('Ok', D('9'), D('10'), True), sc.entra_en_reposicion('Ok', D('10'), D('10'), True)), (True, False))

PROV_A = {'id': 1, 'nombre': 'Verduleria Sol'}
PROV_B = {'id': 2, 'nombre': 'Almacen Central'}
FILAS = [
    {'id': 1, 'nombre': 'Tomate', 'tipo_medida': 'Masa', 'estado': 'Critico', 'porcentaje': D('10'), 'stock': D('1000'), 'objetivo': D('10000'),
     'costo': D('0.005'), 'proveedor': PROV_A, 'rinde': None},
    {'id': 2, 'nombre': 'Cebolla', 'tipo_medida': 'Masa', 'estado': 'Agotado', 'porcentaje': D('0'), 'stock': D('0'), 'objetivo': D('5000'),
     'costo': D('0.002'), 'proveedor': PROV_A, 'rinde': None},
    {'id': 5, 'nombre': 'Harina', 'tipo_medida': 'Masa', 'estado': 'Bajo', 'porcentaje': D('40'), 'stock': D('4000'), 'objetivo': D('10000'),
     'costo': D('0.001'), 'proveedor': PROV_B, 'rinde': None},
    {'id': 6, 'nombre': 'Sal', 'tipo_medida': 'Masa', 'estado': 'Agotado', 'porcentaje': D('0'), 'stock': D('0'), 'objetivo': D('2000'),
     'costo': None, 'proveedor': None, 'rinde': None},
    {'id': 7, 'nombre': 'Aceite', 'tipo_medida': 'Volumen', 'estado': 'Ok', 'porcentaje': D('90'), 'stock': D('9000'), 'objetivo': D('10000'),
     'costo': D('0.01'), 'proveedor': PROV_B, 'rinde': None},
    {'id': 10, 'nombre': 'Salsa base', 'tipo_medida': 'Masa', 'estado': 'Critico', 'porcentaje': D('15'), 'stock': D('300'), 'objetivo': D('2000'),
     'costo': None, 'proveedor': None, 'rinde': D('1000')},
]
plan = sc.plan_reposicion(FILAS)
chequear('proveedores por nombre y "sin proveedor" al final', [(g['proveedor'] or {}).get('nombre') for g in plan['comprar']],
         ['Almacen Central', 'Verduleria Sol', None])
verduleria = next(g for g in plan['comprar'] if g['proveedor'] == PROV_A)
chequear('dentro de un proveedor, lo mas grave primero', [i['nombre'] for i in verduleria['items']], ['Cebolla', 'Tomate'])
chequear('costo estimado a la ultima compra: 9000 g x 0,005 + 5000 g x 0,002', (verduleria['total_estimado'], verduleria['completo']),
         (D('55.00'), True))
sin_proveedor = next(g for g in plan['comprar'] if g['proveedor'] is None)
chequear('un insumo sin costo conocido deja el total incompleto', (sin_proveedor['total_estimado'], sin_proveedor['completo'],
                                                                    sin_proveedor['items'][0]['costo_estimado']), (D('0.00'), False, None))
chequear('el que esta en verde no se pide', 'Aceite' in [i['nombre'] for g in plan['comprar'] for i in g['items']], False)
chequear('lo que se elabora va aparte, con las tandas', [(i['nombre'], i['faltante'], i['tandas']) for i in plan['producir']],
         [('Salsa base', D('1700'), 2)])
chequear('lo elaborado no aparece en lo que se compra', 'Salsa base' in [i['nombre'] for g in plan['comprar'] for i in g['items']], False)
plan_todos = sc.plan_reposicion(FILAS, todos=True)
chequear('con todos=True entra tambien el que esta en verde pero bajo su objetivo',
         'Aceite' in [i['nombre'] for g in plan_todos['comprar'] for i in g['items']], True)

print('Notificaciones: los tipos nuevos se ordenan y se cuentan')
nots = [
    {'tipo': 'lote_por_vencer', 'severidad': 'aviso', 'mensaje': 'b'},
    {'tipo': 'lote_vencido', 'severidad': 'urgente', 'mensaje': 'a'},
    {'tipo': 'elaboracion_a_producir', 'severidad': 'aviso', 'mensaje': 'c'},
    {'tipo': 'insumo_critico', 'severidad': 'aviso', 'mensaje': 'd'},
]
chequear('urgente primero; a igual severidad, por tipo', [n['tipo'] for n in sorted(nots, key=sc.clave_notificacion)],
         ['lote_vencido', 'insumo_critico', 'lote_por_vencer', 'elaboracion_a_producir'])
resumen = sc.resumen_notificaciones(nots)
chequear('el resumen cuenta los tipos nuevos', (resumen['total'], resumen['por_tipo']['lote_por_vencer'], resumen['por_tipo']['elaboracion_a_producir'],
                                              resumen['por_tipo']['lote_vencido']), (4, 1, 1, 1))

ok = sum(RESULTADOS)
print(f'\nResultado: {ok}/{len(RESULTADOS)} correctas')
sys.exit(0 if ok == len(RESULTADOS) else 1)
