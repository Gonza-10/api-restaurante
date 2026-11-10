"""Prueba de la lista de reposicion (hito 6.1) que no usa la base de datos: stock util (lo que va a vencer no cuenta),
verificacion de los ingredientes de cada elaboracion (en cadena) y aviso de vencimiento propio de cada insumo. Solo
libreria estandar; no hace falta tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_reposicion_calculos.py
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


def fila(id, nombre, stock, objetivo, medida='Masa', a_perder=0, vencido=0, bajo=50, critico=20, proveedor=None, activo=True):
    return {
        'id': id, 'nombre': nombre, 'tipo_medida': medida, 'activo': activo, 'stock': D(str(stock)), 'objetivo': D(str(objetivo)),
        'a_perder': D(str(a_perder)), 'vencido': D(str(vencido)), 'umbral_bajo': bajo, 'umbral_critico': critico,
        'proveedor': proveedor,
    }


def items_comprar(plan):
    return {i['nombre']: i for g in plan['comprar'] for i in g['items']}


def items_producir(plan):
    return {i['nombre']: i for i in plan['producir']}


COSTOS = {1: D('0.005'), 2: D('0.002'), 3: D('0.01'), 4: D('5'), 5: D('0.001')}
costo_de = COSTOS.get

print('Aviso de vencimiento propio de cada insumo')
chequear('sin dias propios usa los generales', sc.ventana_aviso(None, 5), 5)
chequear('con dias propios usa los suyos (tomate 2, harina 30)', (sc.ventana_aviso(2, 5), sc.ventana_aviso(30, 5)), (2, 30))
chequear('0 dias propios vale: avisa recien el dia que vence', sc.ventana_aviso(0, 5), 0)
chequear('el mismo lote, 4 dias antes: avisa con 5 y 30, no con 2',
         [sc.estado_vencimiento(4, sc.ventana_aviso(p, 5)) for p in (None, 30, 2)], ['por_vencer', 'por_vencer', None])
chequear('vence hoy avisa aun con 0 dias; ayer ya esta vencido',
         (sc.estado_vencimiento(0, 0), sc.estado_vencimiento(-1, 0)), ('por_vencer', 'vencido'))

print('Estado del stock (misma regla que la vista vw_StockInsumo)')
chequear('sin stock: Agotado', sc.estado_de_stock(D('0'), D('100'), 50, 20), ('Agotado', D('0.0')))
chequear('20 % o menos: Critico', sc.estado_de_stock(D('20'), D('100'), 50, 20), ('Critico', D('20.0')))
chequear('mas de 20 % hasta 50 %: Bajo', (sc.estado_de_stock(D('21'), D('100'), 50, 20)[0], sc.estado_de_stock(D('50'), D('100'), 50, 20)[0]),
         ('Bajo', 'Bajo'))
chequear('mas de 50 %: Ok', sc.estado_de_stock(D('51'), D('100'), 50, 20), ('Ok', D('51.0')))
chequear('sin objetivo: SinObjetivo', sc.estado_de_stock(D('5'), D('0'), 50, 20), ('SinObjetivo', None))
chequear('el porcentaje se redondea a un decimal', sc.estado_de_stock(D('1'), D('3'), 50, 20)[1], D('33.3'))

print('Hueco A: lo que se va a perder no cuenta como stock')
sin_perdida = sc.plan_reposicion([fila(5, 'Harina', 10000, 15000)], costo_de=costo_de)
chequear('10 kg de 15 kg (66,7 %) esta Ok: no se repone', sin_perdida['comprar'], [])
con_perdida = sc.plan_reposicion([fila(5, 'Harina', 10000, 15000, a_perder=6000)], costo_de=costo_de)
harina = items_comprar(con_perdida)['Harina']
chequear('si 6 kg vencen pronto, solo hay 4 kg utiles (26,7 %): Bajo y se repone',
         (harina['estado'], harina['porcentaje'], harina['stock'], harina['a_perder'], harina['stock_util']),
         ('Bajo', D('26.7'), D('10000'), D('6000'), D('4000')))
chequear('se piden 11 kg (15 - 4), no 5 kg', (harina['faltante'], harina['costo_estimado']), (D('11000.000'), D('11.00')))
todo_vencido = sc.plan_reposicion([fila(5, 'Harina', 3000, 15000, a_perder=3000, vencido=3000)], costo_de=costo_de)
chequear('si todo el stock esta vencido, esta Agotado y se pide el objetivo completo',
         (items_comprar(todo_vencido)['Harina']['estado'], items_comprar(todo_vencido)['Harina']['faltante']), ('Agotado', D('15000.000')))
exceso = sc.plan_reposicion([fila(5, 'Harina', 1000, 15000, a_perder=9999)], costo_de=costo_de)
chequear('lo a perder nunca supera al stock (no queda un stock util negativo)', items_comprar(exceso)['Harina']['stock_util'], D('0'))

print('Hueco B: elaborar necesita ingredientes')
# insumos: 1 tomate, 3 aceite, 4 aji (u), 10 salsa base, 11 salsa picante
RECETAS = {
    10: {'rinde': D('1000'), 'ingredientes': [(1, D('800')), (3, D('50'))]},
    11: {'rinde': D('500'), 'ingredientes': [(10, D('500')), (4, D('2'))]},
}
filas_b = [
    fila(1, 'Tomate', 1000, 1200, proveedor={'id': 1, 'nombre': 'Verduleria'}),
    fila(3, 'Aceite', 5000, 5000, 'Volumen', proveedor={'id': 1, 'nombre': 'Verduleria'}),
    fila(10, 'Salsa base', 300, 2000),
]
b = sc.plan_reposicion(filas_b, {10: RECETAS[10]}, costo_de=costo_de)
salsa = items_producir(b)['Salsa base']
chequear('la salsa baja pide 2 tandas (1700 g / 1000 g, redondeo hacia arriba)', (salsa['faltante'], salsa['tandas'], salsa['cantidad_a_producir']),
         (D('1700'), 2, D('2000.000')))
chequear('con 1000 g de tomate solo alcanza para 1 tanda (800 g)', (salsa['tandas_posibles'], salsa['alcanza']), (1, False))
chequear('dice que ingrediente falta y cuanto: tomate 1600 necesarios, 1000 disponibles, faltan 600',
         [(f['nombre'], f['necesario'], f['disponible'], f['faltante'], f['accion']) for f in salsa['ingredientes_faltantes']],
         [('Tomate', D('1600.000'), D('1000'), D('600.000'), 'comprar')])
tomate = items_comprar(b)['Tomate']
chequear('el tomate que falta se suma a las compras aunque este Ok por su cuenta (83 %)',
         (tomate['estado'], tomate['faltante'], tomate['faltante_por_objetivo'], tomate['faltante_para_elaborar']),
         ('Ok', D('600.000'), D('0'), D('600.000')))
chequear('y dice para que elaboracion es', [(q['nombre'], q['cantidad']) for q in tomate['para_elaborar']], [('Salsa base', D('1600'))])
chequear('el aceite alcanza y no se compra', 'Aceite' in items_comprar(b), False)
chequear('costo del faltante: 600 g x 0,005', tomate['costo_estimado'], D('3.00'))

alcanza = sc.plan_reposicion([fila(1, 'Tomate', 5000, 5000), fila(3, 'Aceite', 5000, 5000, 'Volumen'), fila(10, 'Salsa base', 300, 2000)],
                             {10: RECETAS[10]}, costo_de=costo_de)
chequear('si los ingredientes alcanzan, no se compra nada y lo elaborable queda marcado como posible',
         (alcanza['comprar'], items_producir(alcanza)['Salsa base']['alcanza'], items_producir(alcanza)['Salsa base']['ingredientes_faltantes']),
         ([], True, []))

mas_grande = sc.plan_reposicion([fila(1, 'Tomate', 1000, 10000), fila(3, 'Aceite', 5000, 5000, 'Volumen'), fila(10, 'Salsa base', 300, 2000)],
                                {10: RECETAS[10]}, costo_de=costo_de)
t2 = items_comprar(mas_grande)['Tomate']
chequear('si el tomate ya esta bajo, se pide lo mayor entre llegar al objetivo (9000) y lo que necesita la salsa (600)',
         (t2['faltante'], t2['faltante_por_objetivo'], t2['faltante_para_elaborar']), (D('9000.000'), D('9000'), D('600.000')))

vencido = sc.plan_reposicion([fila(1, 'Tomate', 1000, 1200, a_perder=400, vencido=400), fila(3, 'Aceite', 5000, 5000, 'Volumen'),
                              fila(10, 'Salsa base', 300, 2000)], {10: RECETAS[10]}, costo_de=costo_de)
chequear('el tomate ya vencido no sirve para cocinar: disponible 600, para 1600 faltan 1000',
         [(f['disponible'], f['faltante']) for f in items_producir(vencido)['Salsa base']['ingredientes_faltantes']], [(D('600'), D('1000.000'))])
por_vencer = sc.plan_reposicion([fila(1, 'Tomate', 1000, 1200, a_perder=400, vencido=0), fila(3, 'Aceite', 5000, 5000, 'Volumen'),
                                 fila(10, 'Salsa base', 300, 2000)], {10: RECETAS[10]}, costo_de=costo_de)
chequear('el tomate que recien va a vencer todavia sirve para cocinar hoy (disponible 1000)',
         [f['disponible'] for f in items_producir(por_vencer)['Salsa base']['ingredientes_faltantes']], [D('1000')])

print('Elaboraciones que usan otras elaboraciones (en cadena)')
filas_c = [
    fila(1, 'Tomate', 1000, 0), fila(3, 'Aceite', 5000, 0, 'Volumen'), fila(4, 'Aji', 10, 0, 'Unidad'),
    fila(10, 'Salsa base', 300, 0),                 # sin objetivo: solo se produce si otra elaboracion la necesita
    fila(11, 'Salsa picante', 0, 1000),             # agotada: 1000 g / 500 g = 2 tandas
]
c = sc.plan_reposicion(filas_c, RECETAS, costo_de=costo_de)
picante = items_producir(c)['Salsa picante']
base = items_producir(c)['Salsa base']
chequear('la picante agotada pide 2 tandas', (picante['tandas'], picante['por_objetivo']), (2, True))
chequear('que consumen 1000 g de salsa base y 4 ajies', sorted((f['nombre'], f['necesario'], f['accion']) for f in picante['ingredientes_faltantes']),
         [('Salsa base', D('1000.000'), 'producir')])
chequear('la salsa base (sin objetivo) se pide igual: solo hay 300 g y faltan 700 g = 1 tanda',
         (base['tandas'], base['por_objetivo'], [(q['nombre'], q['cantidad']) for q in base['para_elaborar']]),
         (1, False, [('Salsa picante', D('1000.000'))]))
chequear('para esa tanda alcanza el tomate (800 g de 1000 g)', (base['alcanza'], base['ingredientes_faltantes']), (True, []))
chequear('se cocina primero lo que otras elaboraciones usan: salsa base antes que salsa picante',
         [i['nombre'] for i in c['producir']], ['Salsa base', 'Salsa picante'])
chequear('el aji alcanza (4 de 10): no se compra', 'Aji' in items_comprar(c), False)

filas_d = [fila(1, 'Tomate', 500, 0), fila(3, 'Aceite', 5000, 0, 'Volumen'), fila(4, 'Aji', 1, 0, 'Unidad'),
           fila(10, 'Salsa base', 0, 0), fila(11, 'Salsa picante', 0, 1000)]
d = sc.plan_reposicion(filas_d, RECETAS, costo_de=costo_de)
chequear('la falta llega hasta la materia prima: la picante usa 1000 g de base -> 1 tanda de base -> 800 g de tomate, hay 500 -> comprar 300',
         (items_producir(d)['Salsa base']['tandas'], items_comprar(d)['Tomate']['faltante']), (1, D('300.000')))
chequear('y el aji (4 necesarios, hay 1) se compra: faltan 3', items_comprar(d)['Aji']['faltante'], D('3.000'))
chequear('costo del faltante de aji: 3 u x 5', items_comprar(d)['Aji']['costo_estimado'], D('15.00'))

print('Lo que se mantiene de antes')
PROV_A = {'id': 1, 'nombre': 'Verduleria Sol'}
PROV_B = {'id': 2, 'nombre': 'Almacen Central'}
filas_e = [
    fila(1, 'Tomate', 1000, 10000, proveedor=PROV_A), fila(2, 'Cebolla', 0, 5000, proveedor=PROV_A),
    fila(5, 'Harina', 4000, 10000, proveedor=PROV_B), fila(6, 'Sal', 0, 2000), fila(7, 'Aceite', 9000, 10000, 'Volumen', proveedor=PROV_B),
    fila(10, 'Salsa base', 300, 2000),
    fila(20, 'Pimienta', 0, 500, activo=False),
]
e = sc.plan_reposicion(filas_e, {10: {'rinde': D('1000'), 'ingredientes': []}}, costo_de=costo_de)
chequear('proveedores por nombre y "sin proveedor" al final', [(g['proveedor'] or {}).get('nombre') for g in e['comprar']],
         ['Almacen Central', 'Verduleria Sol', None])
verduleria = next(g for g in e['comprar'] if g['proveedor'] == PROV_A)
chequear('dentro de un proveedor, lo mas grave primero', [i['nombre'] for i in verduleria['items']], ['Cebolla', 'Tomate'])
chequear('costo estimado a la ultima compra: 9000 g x 0,005 + 5000 g x 0,002', (verduleria['total_estimado'], verduleria['completo']),
         (D('55.00'), True))
sin_prov = next(g for g in e['comprar'] if g['proveedor'] is None)
chequear('un insumo sin costo conocido deja el total incompleto',
         (sin_prov['total_estimado'], sin_prov['completo'], sin_prov['items'][0]['costo_estimado']), (D('0.00'), False, None))
chequear('el que esta en verde no se pide', 'Aceite' in items_comprar(e), False)
chequear('un insumo dado de baja no se pide', 'Pimienta' in items_comprar(e), False)
chequear('lo que se elabora va aparte, con las tandas', [(i['nombre'], i['faltante'], i['tandas']) for i in e['producir']], [('Salsa base', D('1700'), 2)])
chequear('lo elaborado no aparece en lo que se compra', 'Salsa base' in items_comprar(e), False)
todos = sc.plan_reposicion(filas_e, {10: {'rinde': D('1000'), 'ingredientes': []}}, todos=True, costo_de=costo_de)
chequear('con todos=True entra tambien el que esta en verde pero bajo su objetivo', 'Aceite' in items_comprar(todos), True)
chequear('una elaboracion que no hay que producir no aparece',
         sc.plan_reposicion([fila(10, 'Salsa base', 2000, 2000)], {10: {'rinde': D('1000'), 'ingredientes': []}})['producir'], [])
chequear('orden de cocina (arriba hacia abajo)', sc.orden_elaboraciones(RECETAS), [11, 10])
chequear('profundidad: la base usa solo insumos comprados (0), la picante usa una elaboracion (1)',
         (sc.profundidad_elaboracion(10, RECETAS), sc.profundidad_elaboracion(11, RECETAS)), (0, 1))

ok = sum(RESULTADOS)
print(f'\nResultado: {ok}/{len(RESULTADOS)} correctas')
sys.exit(0 if ok == len(RESULTADOS) else 1)
