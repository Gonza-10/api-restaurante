"""Extras por receta (cobros, hito 5): el cliente le suma a un plato algo mas, con recargo ("mas cheddar", "aderezo").

- Que extras ofrece un plato lo decide Admin/Gerente en su RECETA (RecetaExtra): insumo, cuanto gasta y cuanto cuesta
  una unidad de extra, y cuantas unidades admite cada plato.
- El pedido lleva, por cada unidad de plato, la lista de extras: {"id": producto, "extras": [{"id": id_extra, "cantidad": 2}]}.
- El extra gasta stock (se suma a la receta del plato, ver stock_calculos.receta_con_extras) y suma su recargo al precio
  del renglon. Queda registrado en PedidoDetalleExtra con el recargo congelado.
- Un extra sin stock para una unidad no se ofrece (RecetaExtra.disponible, lo mantiene recetas.recalcular_disponibilidad).
- Como el plato, el extra se cobra al precio que el cliente vio (el menor entre el vigente y el visto).
"""
from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from .models import Producto, RecetaExtra

CENTAVOS = Decimal('0.01')


def clave_precio_extra(id_extra):
    """Clave del extra en los precios vistos del menu (los platos usan su id; los extras, 'x' + id)."""
    return f'x{id_extra}'


def _json_extra(extra, completo):
    datos = {
        'id': extra.id, 'nombre': extra.insumo.nombre, 'precio': str(extra.precio.quantize(CENTAVOS)),
        'max_por_unidad': extra.max_por_unidad,
    }
    if completo:   # Admin/Gerente: tambien lo que el cliente no ve
        datos.update({'insumo': extra.insumo_id, 'cantidad': str(extra.cantidad), 'activo': extra.activo, 'disponible': extra.disponible})
    return datos


def extras_de_productos(ids_producto=None, ofrecibles=True):
    """{id_producto: [extra]} con los extras de la receta de cada plato (solo aparecen los platos que tienen alguno).
    ofrecibles=True (el menu del cliente): solo los activos y con stock. False: todos, con sus datos de gestion."""
    productos = Producto.objects.filter(receta__isnull=False)
    if ids_producto is not None:
        productos = productos.filter(id__in=list(ids_producto))
    recetas_por_producto = dict(productos.values_list('id', 'receta_id'))
    consulta = RecetaExtra.objects.filter(receta_id__in=set(recetas_por_producto.values())).select_related('insumo')
    if ofrecibles:
        consulta = consulta.filter(activo=True, disponible=True)
    por_receta = defaultdict(list)
    for extra in consulta:
        por_receta[extra.receta_id].append(extra)
    return {
        id_producto: [_json_extra(e, not ofrecibles) for e in sorted(por_receta[id_receta], key=lambda e: e.insumo.nombre.lower())]
        for id_producto, id_receta in recetas_por_producto.items() if por_receta[id_receta]
    }


def problemas_de_extras(items, extras, recetas):
    """Logica pura de validar_extras. extras: {id_extra: objeto con receta_id, activo, disponible, max_por_unidad, insumo_id y
    insumo.nombre}; recetas: {id_producto: id_receta}. Devuelve la lista de problemas, sin repetir."""
    problemas, vistos = [], set()
    for item in items:
        for pedido in (item.get('extras') or []):
            extra = extras.get(pedido['id'])
            if extra is None:
                motivo = 'no_existe'
            elif extra.receta_id != recetas.get(item['id']):
                motivo = 'no_pertenece'
            elif not extra.activo:
                motivo = 'fuera_de_carta'
            elif not extra.disponible:
                motivo = 'sin_stock'
            elif pedido['cantidad'] > extra.max_por_unidad:
                motivo = 'excede_maximo'
            elif extra.insumo_id in set(item.get('sin') or ()):
                motivo = 'incompatible_con_sin'
            else:
                continue
            if (item['id'], pedido['id'], motivo) not in vistos:
                vistos.add((item['id'], pedido['id'], motivo))
                problemas.append({'id': item['id'], 'extra': pedido['id'], 'nombre': extra.insumo.nombre if extra else None, 'motivo': motivo})
    return problemas


def validar_extras(items):
    """Comprueba que cada extra pedido se pueda pedir para ese plato. items: [{'id': producto, 'sin': [...], 'extras':
    [{'id': id_extra, 'cantidad': n}]}]. Devuelve los problemas ([] si todo esta bien):
    [{'id': producto, 'extra': id_extra, 'nombre': nombre del extra o None, 'motivo': ...}] con motivo
    no_existe | no_pertenece | fuera_de_carta | sin_stock | excede_maximo | incompatible_con_sin."""
    pedidos = [(item['id'], e) for item in items for e in (item.get('extras') or [])]
    if not pedidos:
        return []
    extras = {x.id: x for x in RecetaExtra.objects.filter(id__in={e['id'] for _, e in pedidos}).select_related('insumo')}
    recetas = dict(Producto.objects.filter(id__in={i for i, _ in pedidos}).values_list('id', 'receta_id'))
    return problemas_de_extras(items, extras, recetas)


def extras_de_detalle(detalle):
    """Extras de un renglon del pedido: [{'nombre', 'cantidad', 'precio'}] ordenados por nombre. Usar con
    prefetch_related('detalles__extras__insumo') para no hacer una consulta por renglon."""
    return sorted(
        ({'nombre': e.insumo.nombre, 'cantidad': e.cantidad, 'precio': e.precio_unitario} for e in detalle.extras.all()),
        key=lambda e: e['nombre'].lower(),
    )


def texto_extras(detalle):
    """Los extras de un renglon como texto corto para Cocina y el ticket: ['Cheddar', 'Aderezo x2']."""
    return [e['nombre'] + (f" x{e['cantidad']}" if e['cantidad'] > 1 else '') for e in extras_de_detalle(detalle)]


@transaction.atomic
def copiar_extras(receta_origen, receta_destino):
    """Copia los extras de una receta a otra (por insumo): los que el destino ya tiene NO se pisan. Devuelve
    (copiados, omitidos), cada uno una lista de nombres de insumo."""
    existentes = set(RecetaExtra.objects.filter(receta=receta_destino).values_list('insumo_id', flat=True))
    copiados, omitidos, nuevos = [], [], []
    for extra in RecetaExtra.objects.filter(receta=receta_origen).select_related('insumo').order_by('insumo__nombre'):
        if extra.insumo_id in existentes:
            omitidos.append(extra.insumo.nombre)
            continue
        nuevos.append(RecetaExtra(
            receta=receta_destino, insumo=extra.insumo, cantidad=extra.cantidad, precio=extra.precio,
            max_por_unidad=extra.max_por_unidad, activo=extra.activo, disponible=extra.disponible,
        ))
        copiados.append(extra.insumo.nombre)
    RecetaExtra.objects.bulk_create(nuevos)
    return copiados, omitidos
