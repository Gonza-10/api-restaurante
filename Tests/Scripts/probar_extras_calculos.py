"""Prueba de los calculos de los extras por receta (cobros, hito 5) que no usan la base de datos: clave de linea, receta con
extras, si alcanza el stock, precio del renglon, descripcion en la factura y las reglas de validacion de un extra.
Solo libreria estandar; no hace falta tener corriendo nada.

Uso (PowerShell, en la raiz del proyecto):
    python Tests\\Scripts\\probar_extras_calculos.py
"""
import importlib
import importlib.util
import sys
import types
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as NS

CARPETA = Path(__file__).resolve().parents[2] / 'restaurante'


def cargar(nombre):
    spec = importlib.util.spec_from_file_location(f'restaurante.{nombre}', CARPETA / f'{nombre}.py')
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[f'restaurante.{nombre}'] = modulo
    spec.loader.exec_module(modulo)
    return modulo


# extras.py importa modelos de Django: se reemplazan por dobles vacios (aca solo se prueba la logica pura)
paquete = types.ModuleType('restaurante'); paquete.__path__ = [str(CARPETA)]; sys.modules['restaurante'] = paquete
modelos = types.ModuleType('restaurante.models'); modelos.Producto = object; modelos.RecetaExtra = object; sys.modules['restaurante.models'] = modelos
django = types.ModuleType('django'); django_db = types.ModuleType('django.db')
django_db.transaction = NS(atomic=lambda f: f); django.db = django_db
sys.modules['django'] = django; sys.modules['django.db'] = django_db

sc = cargar('stock_calculos')
ex = cargar('extras')

RESULTADOS = []


def chequear(nombre, obtenido, esperado):
    ok = obtenido == esperado
    RESULTADOS.append(ok)
    print(('OK   ' if ok else 'FALLA'), nombre, '' if ok else f'-> obtenido {obtenido!r}, esperado {esperado!r}')


# ---------- clave de linea ----------
chequear('sin extras la clave es la de siempre', sc.clave_de_linea(7, [3, 1]), (7, (1, 3)))
chequear('con extras suma un tercer elemento ordenado', sc.clave_de_linea(7, [], [(5, 2), (2, 1)]), (7, (), ((2, 1), (5, 2))))
chequear('el orden de los extras no cambia la clave', sc.clave_de_linea(7, [], [(5, 2), (2, 1)]) == sc.clave_de_linea(7, [], [(2, 1), (5, 2)]), True)
chequear('distinta cantidad de extra = otra linea', sc.clave_de_linea(7, [], [(2, 1)]) == sc.clave_de_linea(7, [], [(2, 2)]), False)
chequear('id de la linea con extras', sc.id_de_linea(sc.clave_de_linea(7, [], [(2, 1)])), 7)
chequear('quitados de la linea con extras', sc.sin_de_linea(sc.clave_de_linea(7, [4], [(2, 1)])), (4,))
chequear('extras de la linea', sc.extras_de_linea(sc.clave_de_linea(7, [], [(2, 1)])), ((2, 1),))
chequear('extras de una linea sin extras', sc.extras_de_linea(sc.clave_de_linea(7, [4])), ())
chequear('extras de una linea que es solo el id', sc.extras_de_linea(7), ())

# ---------- receta con extras ----------
HAMBURGUESA = [(1, D('1')), (2, D('20')), (3, D('150'))]    # pan (u), cheddar (g), carne (g)
chequear('un extra de un insumo que la receta ya usa se suma a esa linea',
         dict(sc.receta_con_extras(HAMBURGUESA, [(2, D('30'))])), {1: D('1'), 2: D('50'), 3: D('150')})
chequear('un extra de un insumo nuevo se agrega',
         dict(sc.receta_con_extras(HAMBURGUESA, [(9, D('15'))])), {1: D('1'), 2: D('20'), 3: D('150'), 9: D('15')})
chequear('dos extras del mismo insumo se suman', dict(sc.receta_con_extras(HAMBURGUESA, [(9, D('15')), (9, D('5'))]))[9], D('20'))
chequear('la receta original no se modifica', HAMBURGUESA, [(1, D('1')), (2, D('20')), (3, D('150'))])
chequear('el extra sobre un ingrediente quitado lo vuelve a agregar',
         dict(sc.receta_con_extras(sc.receta_efectiva(HAMBURGUESA, [2]), [(2, D('30'))]))[2], D('30'))

# ---------- alcanza el stock? ----------
linea_extra = sc.clave_de_linea(7, [], [(2, 1)])
simple = sc.clave_de_linea(7)
recetas = {simple: HAMBURGUESA, linea_extra: sc.receta_con_extras(HAMBURGUESA, [(2, D('30'))])}
disponible = {1: D('10'), 2: D('100'), 3: D('1000')}
chequear('2 hamburguesas con extra cheddar usan 100 g de cheddar',
         sc.requerimiento_por_insumo({linea_extra: 2}, recetas)[2], D('100'))
chequear('con 100 g alcanza para 2 con extra', sc.evaluar_pedido({linea_extra: 2}, recetas, disponible), [])
faltantes = sc.evaluar_pedido({linea_extra: 3}, recetas, disponible)
chequear('con 100 g no alcanza para 3: se pueden preparar 2',
         [(f['id_producto'], f['pedido'], f['posibles'], f['id_insumo_limitante']) for f in faltantes], [(7, 3, 2, 2)])
chequear('simples y con extra comparten el cheddar: 1 con extra (50) + 3 simples (60) = 110 > 100',
         len(sc.evaluar_pedido({simple: 3, linea_extra: 1}, recetas, disponible)), 1)
chequear('1 con extra (50) + 2 simples (40) = 90 alcanza', sc.evaluar_pedido({simple: 2, linea_extra: 1}, recetas, disponible), [])

# ---------- precio del renglon y descripcion ----------
chequear('precio del renglon: plato + recargos', sc.precio_de_renglon(D('10000'), [(D('500'), 2), (D('300'), 1)]), D('11300'))
chequear('sin extras el precio es el del plato', sc.precio_de_renglon(D('10000'), []), D('10000'))
chequear('un extra gratis no cambia el precio', sc.precio_de_renglon(D('10000'), [(D('0'), 1)]), D('10000'))
# (la descripcion de la factura con extras se prueba en probar_cuenta_calculos.py)

# ---------- validacion de un extra ----------
def extra(id_extra, receta=10, activo=True, disponible=True, maximo=2, insumo=2, nombre='Cheddar'):
    return NS(id=id_extra, receta_id=receta, activo=activo, disponible=disponible, max_por_unidad=maximo,
              insumo_id=insumo, insumo=NS(nombre=nombre))


EXTRAS = {1: extra(1), 2: extra(2, activo=False), 3: extra(3, disponible=False), 4: extra(4, receta=99), 5: extra(5, insumo=4, nombre='Cebolla')}
RECETAS = {7: 10, 8: None}


def problemas(items):
    return [(p['id'], p['extra'], p['motivo']) for p in ex.problemas_de_extras(items, EXTRAS, RECETAS)]


chequear('un extra valido no tiene problemas', problemas([{'id': 7, 'extras': [{'id': 1, 'cantidad': 2}]}]), [])
chequear('pedido sin extras', problemas([{'id': 7}, {'id': 7, 'extras': []}]), [])
chequear('extra que no existe', problemas([{'id': 7, 'extras': [{'id': 99, 'cantidad': 1}]}]), [(7, 99, 'no_existe')])
chequear('extra de otra receta', problemas([{'id': 7, 'extras': [{'id': 4, 'cantidad': 1}]}]), [(7, 4, 'no_pertenece')])
chequear('extra en un plato sin receta', problemas([{'id': 8, 'extras': [{'id': 1, 'cantidad': 1}]}]), [(8, 1, 'no_pertenece')])
chequear('extra desactivado', problemas([{'id': 7, 'extras': [{'id': 2, 'cantidad': 1}]}]), [(7, 2, 'fuera_de_carta')])
chequear('extra sin stock', problemas([{'id': 7, 'extras': [{'id': 3, 'cantidad': 1}]}]), [(7, 3, 'sin_stock')])
chequear('mas del maximo por unidad', problemas([{'id': 7, 'extras': [{'id': 1, 'cantidad': 3}]}]), [(7, 1, 'excede_maximo')])
chequear('extra y "sin" del mismo insumo', problemas([{'id': 7, 'sin': [4], 'extras': [{'id': 5, 'cantidad': 1}]}]), [(7, 5, 'incompatible_con_sin')])
chequear('"sin" de otro insumo no molesta', problemas([{'id': 7, 'sin': [3], 'extras': [{'id': 1, 'cantidad': 1}]}]), [])
chequear('el mismo problema en dos unidades se informa una vez',
         problemas([{'id': 7, 'extras': [{'id': 3, 'cantidad': 1}]}, {'id': 7, 'extras': [{'id': 3, 'cantidad': 1}]}]), [(7, 3, 'sin_stock')])
chequear('el problema trae el nombre del extra', ex.problemas_de_extras([{'id': 7, 'extras': [{'id': 3, 'cantidad': 1}]}], EXTRAS, RECETAS)[0]['nombre'], 'Cheddar')
chequear('un extra inexistente no trae nombre', ex.problemas_de_extras([{'id': 7, 'extras': [{'id': 99, 'cantidad': 1}]}], EXTRAS, RECETAS)[0]['nombre'], None)

# ---------- texto de los extras de un renglon ----------
def detalle(*extras):
    filas = [NS(insumo=NS(nombre=n), cantidad=c, precio_unitario=D(p)) for n, c, p in extras]
    return NS(extras=NS(all=lambda: filas))


chequear('texto para cocina', ex.texto_extras(detalle(('Cheddar', 2, '500'), ('aderezo', 1, '300'))), ['aderezo', 'Cheddar x2'])
chequear('renglon sin extras', ex.texto_extras(detalle()), [])
chequear('extras del historial', ex.extras_de_detalle(detalle(('Cheddar', 2, '500'))), [{'nombre': 'Cheddar', 'cantidad': 2, 'precio': D('500')}])
chequear('clave de precio de un extra', ex.clave_precio_extra(12), 'x12')

total = len(RESULTADOS)
print(f'\nResultado: {sum(RESULTADOS)}/{total} correctas')
sys.exit(0 if all(RESULTADOS) else 1)
