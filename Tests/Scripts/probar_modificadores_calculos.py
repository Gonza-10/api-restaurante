"""Prueba de los calculos de modificadores ("sin cebolla") que no usan la base de datos: receta efectiva, lineas de
pedido y si alcanza el stock cuando se quita un ingrediente. Solo libreria estandar; no hace falta tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_modificadores_calculos.py
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


# insumos: 1 = carne (g), 2 = cebolla (g, QUITABLE), 3 = pan (u). Producto 10 = milanesa, 20 = una gaseosa sin receta.
MILANESA = [(1, D('200')), (2, D('30')), (3, D('1'))]
CEBOLLA = 2

print('Lineas del pedido')
chequear('sin modificadores', sc.clave_de_linea(10), (10, ()))
chequear('los ids quitados quedan ordenados', sc.clave_de_linea(10, [5, 2]), (10, (2, 5)))
chequear('y sin repetidos', sc.clave_de_linea(10, [2, 2]), (10, (2,)))
chequear('pedir lo mismo en distinto orden es la misma linea', sc.clave_de_linea(10, [5, 2]), sc.clave_de_linea(10, [2, 5]))
chequear('con y sin cebolla son lineas distintas', sc.clave_de_linea(10, [2]) != sc.clave_de_linea(10), True)
chequear('id de una linea', (sc.id_de_linea((10, (2,))), sc.id_de_linea(10)), (10, 10))
chequear('quitados de una linea', (sc.sin_de_linea((10, (2,))), sc.sin_de_linea(10)), ((2,), ()))

print('Receta efectiva: la receta sin lo que el cliente quito')
chequear('sin cebolla', sc.receta_efectiva(MILANESA, (CEBOLLA,)), [(1, D('200')), (3, D('1'))])
chequear('sin quitar nada queda igual', sc.receta_efectiva(MILANESA, ()), MILANESA)
chequear('sin lista (None) queda igual', sc.receta_efectiva(MILANESA, None), MILANESA)
chequear('quitar algo que la receta no tiene no cambia nada', sc.receta_efectiva(MILANESA, (99,)), MILANESA)
chequear('no modifica la receta original', (sc.receta_efectiva(MILANESA, (CEBOLLA,)), len(MILANESA)), ([(1, D('200')), (3, D('1'))], 3))

print('Lo que necesita un pedido con modificadores')
recetas = {(10, ()): MILANESA, (10, (CEBOLLA,)): sc.receta_efectiva(MILANESA, (CEBOLLA,))}
chequear('1 comun + 2 sin cebolla: la cebolla solo se cuenta una vez',
         sc.requerimiento_por_insumo({(10, ()): 1, (10, (CEBOLLA,)): 2}, recetas),
         {1: D('600'), 2: D('30'), 3: D('3')})
chequear('3 sin cebolla: no consume cebolla', sc.requerimiento_por_insumo({(10, (CEBOLLA,)): 3}, recetas),
         {1: D('600'), 3: D('3')})
chequear('sigue andando con el id solo (sin modificadores)', sc.requerimiento_por_insumo({10: 2}, {10: MILANESA}),
         {1: D('400'), 2: D('60'), 3: D('2')})

print('Pedido contra stock con modificadores')
STOCK = {1: D('600'), 2: D('30'), 3: D('10')}
chequear('sin cebolla alcanza aunque la cebolla este en cero',
         sc.evaluar_pedido({(10, (CEBOLLA,)): 2}, recetas, {1: D('600'), 2: D('0'), 3: D('10')}), [])
chequear('la comun no alcanza con la cebolla en cero (limita la cebolla)',
         sc.evaluar_pedido({(10, ()): 1}, recetas, {1: D('600'), 2: D('0'), 3: D('10')}),
         [{'id_producto': 10, 'pedido': 1, 'posibles': 0, 'id_insumo_limitante': 2}])
chequear('2 comunes + 2 sin cebolla con cebolla para 1: se informa UN faltante por producto (3 de 4)',
         sc.evaluar_pedido({(10, ()): 2, (10, (CEBOLLA,)): 2}, recetas, STOCK),
         [{'id_producto': 10, 'pedido': 4, 'posibles': 3, 'id_insumo_limitante': 2}])
chequear('las lineas comparten el stock: 4 sin cebolla no alcanzan con carne para 3',
         sc.evaluar_pedido({(10, (CEBOLLA,)): 4}, recetas, STOCK),
         [{'id_producto': 10, 'pedido': 4, 'posibles': 3, 'id_insumo_limitante': 1}])
chequear('1 comun + 2 sin cebolla alcanza justo', sc.evaluar_pedido({(10, ()): 1, (10, (CEBOLLA,)): 2}, recetas, STOCK), [])
chequear('un producto sin receta nunca falta', sc.evaluar_pedido({(20, ()): 5}, recetas, STOCK), [])
chequear('el formato anterior (id de producto) da lo mismo que antes',
         sc.evaluar_pedido({10: 4}, {10: MILANESA}, STOCK),
         [{'id_producto': 10, 'pedido': 4, 'posibles': 1, 'id_insumo_limitante': 2}])
chequear('el mensaje al cliente cuenta las unidades de todas las lineas',
         sc.mensaje_cliente_faltantes(
             sc.evaluar_pedido({(10, ()): 2, (10, (CEBOLLA,)): 2}, recetas, STOCK), {10: 'Milanesa'}),
         'Insumos insuficientes. Podemos preparar solamente 3 de 4 Milanesa. Disculpe las molestias.')

ok = sum(RESULTADOS)
print(f'\nResultado: {ok}/{len(RESULTADOS)} correctas')
sys.exit(0 if ok == len(RESULTADOS) else 1)
