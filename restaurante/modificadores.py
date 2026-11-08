"""Modificadores de los pedidos (hito 5): el cliente pide un plato SIN algun ingrediente ("sin cebolla").

- Que se puede quitar lo decide Admin/Gerente en la receta (RecetaIngrediente.es_quitable); un ingrediente fijo no.
- El pedido lleva, por cada unidad, la lista de insumos que se quitan: {"id": producto, "sin": [id_insumo, ...]}.
- Lo quitado no se descuenta del stock (receta efectiva, ver stock_calculos.receta_efectiva) y queda registrado en
  PedidoDetalleModificador para mostrarlo en Cocina, en el ticket y en el historial de la mesa.
"""
from collections import Counter, defaultdict

from .models import Producto, RecetaIngrediente
from .stock_calculos import clave_de_linea


def quitables_de_productos(ids_producto=None):
    """{id_producto: {id_insumo: nombre}} con los ingredientes que el cliente puede quitar de cada producto (sin
    ids_producto: de todos). Solo aparecen los productos que tienen al menos uno."""
    productos = Producto.objects.filter(receta__isnull=False)
    if ids_producto is not None:
        productos = productos.filter(id__in=list(ids_producto))
    recetas_por_producto = dict(productos.values_list('id', 'receta_id'))
    por_receta = defaultdict(dict)
    for id_receta, id_insumo, nombre in RecetaIngrediente.objects.filter(
        receta_id__in=set(recetas_por_producto.values()), es_quitable=True
    ).values_list('receta_id', 'insumo_id', 'insumo__nombre'):
        por_receta[id_receta][id_insumo] = nombre
    return {
        id_producto: dict(por_receta[id_receta])
        for id_producto, id_receta in recetas_por_producto.items() if por_receta[id_receta]
    }


def quitables_de_receta(id_receta):
    """Ids de los insumos quitables de una receta."""
    return frozenset(
        RecetaIngrediente.objects.filter(receta_id=id_receta, es_quitable=True).values_list('insumo_id', flat=True)
    )


def validar_modificadores(items):
    """Comprueba que cada ingrediente que se quiere quitar se pueda quitar de ese producto.
    items: [{'id': id_producto, 'sin': [id_insumo, ...]}]. Devuelve los problemas ([] si todo esta bien):
    [{'id': id_producto, 'insumo': id_insumo, 'motivo': 'no_quitable'}]."""
    pedidos = {(item['id'], tuple(item.get('sin') or ())) for item in items if item.get('sin')}
    if not pedidos:
        return []
    quitables = quitables_de_productos({id_producto for id_producto, _ in pedidos})
    problemas = []
    for id_producto, sin in sorted(pedidos):
        permitidos = quitables.get(id_producto, {})
        for id_insumo in sin:
            if id_insumo not in permitidos:
                problemas.append({'id': id_producto, 'insumo': id_insumo, 'motivo': 'no_quitable'})
    return problemas


def lineas_de_items(items):
    """{linea: cantidad}: agrupa las unidades pedidas por producto y modificadores (ver stock_calculos.clave_de_linea)."""
    return Counter(
        clave_de_linea(item['id'], item.get('sin'), [(e['id'], e['cantidad']) for e in item.get('extras') or []])
        for item in items
    )


def nombres_quitados(detalle):
    """Nombres de los ingredientes quitados en un renglon del pedido, ordenados. Usar con
    prefetch_related('detalles__modificadores__insumo') para no hacer una consulta por renglon."""
    return sorted((m.insumo.nombre for m in detalle.modificadores.all()), key=str.lower)
