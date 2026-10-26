"""Prueba de los calculos de recetas y descuento por comanda que no usan la base de datos
(porciones que alcanzan, pedido contra stock, mensajes al cliente, costo del plato).
Solo libreria estandar; no hace falta tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_recetas_calculos.py
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


# insumos: 1 = harina (g), 2 = huevo (u), 3 = salsa (ml)
TALLARINES = [(1, D('100')), (2, D('1'))]          # una porcion: 100 g de harina + 1 huevo
PIZZA = [(1, D('250')), (3, D('80'))]              # una porcion: 250 g de harina + 80 ml de salsa
RECETAS = {10: TALLARINES, 20: PIZZA}              # el producto 30 (una gaseosa) no tiene receta

print('Porciones que alcanzan con el stock')
chequear('400 g y 10 huevos = 4 tallarines (limita la harina)',
         sc.porciones_posibles(TALLARINES, {1: D('400'), 2: D('10')}), (4, 1))
chequear('450 g y 3 huevos = 3 (limita el huevo)', sc.porciones_posibles(TALLARINES, {1: D('450'), 2: D('3')}), (3, 2))
chequear('99 g = ninguna (no se redondea hacia arriba)', sc.porciones_posibles(TALLARINES, {1: D('99'), 2: D('50')}), (0, 1))
chequear('insumo sin stock registrado cuenta como cero', sc.porciones_posibles(TALLARINES, {1: D('900')}), (0, 2))
chequear('receta sin ingredientes', sc.porciones_posibles([], {}), (None, None))
chequear('cantidades con decimales', sc.porciones_posibles([(1, D('12.5'))], {1: D('50')}), (4, 1))

print('Lo que necesita un pedido')
chequear('suma el mismo insumo de dos platos', sc.requerimiento_por_insumo({10: 2, 20: 1, 30: 5}, RECETAS),
         {1: D('450'), 2: D('2'), 3: D('80')})
chequear('un producto sin receta no consume', sc.requerimiento_por_insumo({30: 3}, RECETAS), {})

print('Pedido contra stock')
HAY = {1: D('1000'), 2: D('10'), 3: D('500')}
chequear('alcanza todo', sc.evaluar_pedido({10: 4, 20: 2}, RECETAS, HAY), [])
chequear('el producto sin receta nunca falta', sc.evaluar_pedido({30: 99}, RECETAS, {}), [])
chequear('3 de 4 tallarines (alcanza para 3)', sc.evaluar_pedido({10: 4}, RECETAS, {1: D('300'), 2: D('10')}),
         [{'id_producto': 10, 'pedido': 4, 'posibles': 3, 'id_insumo_limitante': 1}])
chequear('ninguno alcanza', sc.evaluar_pedido({10: 1}, RECETAS, {1: D('0'), 2: D('10')}),
         [{'id_producto': 10, 'pedido': 1, 'posibles': 0, 'id_insumo_limitante': 1}])
# 1000 g de harina: 5 tallarines usan 500, quedan 500 -> solo 2 pizzas (250 c/u) de las 3 pedidas
chequear('dos platos comparten harina: no se cuenta dos veces',
         sc.evaluar_pedido({10: 5, 20: 3}, RECETAS, {1: D('1000'), 2: D('10'), 3: D('500')}),
         [{'id_producto': 20, 'pedido': 3, 'posibles': 2, 'id_insumo_limitante': 1}])
chequear('el stock exacto alcanza', sc.evaluar_pedido({10: 2}, RECETAS, {1: D('200'), 2: D('2')}), [])
chequear('falta 1 gramo: no alcanza', sc.evaluar_pedido({10: 2}, RECETAS, {1: D('199.999'), 2: D('2')})[0]['posibles'], 1)
chequear('varios faltantes se informan juntos',
         len(sc.evaluar_pedido({10: 5, 20: 5}, RECETAS, {1: D('300'), 2: D('10'), 3: D('500')})), 2)

print('Mensaje para el cliente: generico, sin decir que insumo falta')
NOMBRES = {10: 'Tallarines', 20: 'Pizza'}
faltante_parcial = [{'id_producto': 10, 'pedido': 4, 'posibles': 3, 'id_insumo_limitante': 1}]
faltante_total = [{'id_producto': 20, 'pedido': 2, 'posibles': 0, 'id_insumo_limitante': 3}]
chequear('3 de 4', sc.mensaje_cliente_faltantes(faltante_parcial, NOMBRES),
         'Insumos insuficientes. Podemos preparar solamente 3 de 4 Tallarines. Disculpe las molestias.')
chequear('ninguno', sc.mensaje_cliente_faltantes(faltante_total, NOMBRES),
         'Insumos insuficientes. Por ahora no podemos preparar Pizza. Disculpe las molestias.')
chequear('dos platos', sc.mensaje_cliente_faltantes(faltante_parcial + faltante_total, NOMBRES),
         'Insumos insuficientes. Podemos preparar solamente 3 de 4 Tallarines. Por ahora no podemos preparar Pizza. '
         'Disculpe las molestias.')
mensaje = sc.mensaje_cliente_faltantes(faltante_parcial, NOMBRES)
chequear('el mensaje al cliente no nombra insumos', 'harina' in mensaje.lower() or 'limita' in mensaje.lower(), False)

print('Motivo interno (solo personal)')
chequear('dice plato, cuantos alcanzan y que insumo limita',
         sc.motivo_interno_faltantes(faltante_parcial, NOMBRES, {1: 'Harina'}),
         'Tallarines: pedidos 4, alcanzan 3; limita Harina')

print('Costo del plato (a costo de reposicion)')
chequear('100 g a 0.002 + 1 huevo a 150', sc.costo_de_receta([(D('100'), D('0.002')), (D('1'), D('150'))]), (D('150.20'), True))
chequear('un insumo sin costo: total parcial y marcado incompleto',
         sc.costo_de_receta([(D('100'), D('0.002')), (D('1'), None)]), (D('0.20'), False))
chequear('costo cero tambien cuenta como incompleto', sc.costo_de_receta([(D('5'), D('0'))])[1], False)

ok = sum(RESULTADOS)
print(f'\nResultado: {ok}/{len(RESULTADOS)} correctas')
sys.exit(0 if ok == len(RESULTADOS) else 1)
