"""Recetas y descuento de stock por comanda (hito 2).

Una receta dice cuanto gasta UNA unidad vendida de cada insumo (en unidad base). Un producto sin receta no lleva
control de stock. Aca vive la parte que toca la base: armar el stock disponible, evaluar un pedido, descontar.
La logica pura (cuantas porciones alcanzan, que mensaje dar) esta en stock_calculos.py y se prueba sola.
"""
from collections import defaultdict

from django.db.models import Sum

from .models import Insumo, LoteInsumo, Producto, RecetaIngrediente
from .stock import descontar_fefo, lotes_fefo, ultimo_costo
from .stock_calculos import (
    CERO, costo_de_receta, evaluar_pedido, mensaje_cliente_faltantes, motivo_interno_faltantes, porciones_posibles,
    redondear_dinero, requerimiento_por_insumo, texto_cantidad,
)


def recetas_de_productos(ids_producto):
    """{id_producto: [(id_insumo, cantidad)]} solo de los productos que tienen receta."""
    ids = list(ids_producto)
    recetas_por_producto = dict(
        Producto.objects.filter(id__in=ids, receta__isnull=False).values_list('id', 'receta_id')
    )
    ingredientes = defaultdict(list)
    for id_receta, id_insumo, cantidad in RecetaIngrediente.objects.filter(
        receta_id__in=set(recetas_por_producto.values())
    ).values_list('receta_id', 'insumo_id', 'cantidad'):
        ingredientes[id_receta].append((id_insumo, cantidad))
    return {id_producto: ingredientes[id_receta] for id_producto, id_receta in recetas_por_producto.items()
            if ingredientes[id_receta]}


def stock_disponible(ids_insumo, bloquear=False):
    """{id_insumo: cantidad} sumando los lotes activos. Con bloquear=True bloquea los lotes (en orden de id, para que
    dos comandas simultaneas no se traben entre si) hasta que termine la transaccion."""
    ids = sorted(set(ids_insumo))
    if not bloquear:
        suma = dict(
            LoteInsumo.objects.filter(insumo_id__in=ids, estado='Activo')
            .values_list('insumo_id').annotate(total=Sum('cantidad_actual'))
        )
        return {i: suma.get(i, CERO) for i in ids}
    return {i: sum((lote.cantidad_actual for lote in lotes_fefo(i, bloquear=True)), CERO) for i in ids}


def evaluar_conteo(conteo, bloquear=False):
    """conteo: {id_producto: cantidad pedida}. Devuelve (faltantes, recetas, disponible)."""
    recetas = recetas_de_productos(conteo)
    ids_insumo = {i for ingredientes in recetas.values() for i, _ in ingredientes}
    disponible = stock_disponible(ids_insumo, bloquear=bloquear)
    return evaluar_pedido(conteo, recetas, disponible), recetas, disponible


def faltantes_para_respuesta(faltantes):
    """Los faltantes con el nombre del producto, para el 409 del carrito."""
    nombres = dict(Producto.objects.filter(id__in=[f['id_producto'] for f in faltantes]).values_list('id', 'nombre'))
    return [
        {'id': f['id_producto'], 'nombre': nombres.get(f['id_producto']), 'pedido': f['pedido'], 'posibles': f['posibles']}
        for f in faltantes
    ], nombres


def mensaje_para_cliente(faltantes):
    _, nombres = faltantes_para_respuesta(faltantes)
    return mensaje_cliente_faltantes(faltantes, nombres)


def motivo_para_personal(faltantes):
    nombres_producto = dict(Producto.objects.filter(id__in=[f['id_producto'] for f in faltantes]).values_list('id', 'nombre'))
    nombres_insumo = dict(Insumo.objects.filter(id__in=[f['id_insumo_limitante'] for f in faltantes]).values_list('id', 'nombre'))
    return motivo_interno_faltantes(faltantes, nombres_producto, nombres_insumo)[:500]


def consumir_pedido(conteo, id_comanda, id_jornada):
    """Descuenta del stock lo que gasta el pedido de una comanda, todo o nada. Debe llamarse dentro de una transaccion
    (la del worker): los lotes quedan bloqueados hasta que termine. Devuelve [] si se desconto, o los faltantes
    (sin descontar nada) si no alcanzaba."""
    faltantes, recetas, _ = evaluar_conteo(conteo, bloquear=True)
    if faltantes:
        return faltantes
    necesario = requerimiento_por_insumo(conteo, recetas)
    insumos = Insumo.objects.in_bulk(necesario.keys())
    for id_insumo in sorted(necesario):  # siempre en el mismo orden: evita bloqueos cruzados entre comandas
        descontar_fefo(insumos[id_insumo], necesario[id_insumo], 'Consumo', id_jornada=id_jornada, id_comanda=id_comanda)
    return []


# ---------- lectura de recetas ----------

def armar_receta(receta, ve_costos, disponible, costos):
    """Representacion de una receta. `disponible` = {id_insumo: stock}, `costos` = {id_insumo: costo de reposicion}.
    Costos y margenes solo los ven Admin y Gerente; Cocina ve cantidades y cuanto se puede preparar."""
    ingredientes = list(receta.ingredientes.all())
    ingredientes.sort(key=lambda i: i.insumo.nombre.lower())
    pares = [(i.insumo_id, i.cantidad) for i in ingredientes]
    posibles, limitante = porciones_posibles(pares, disponible)
    nombre_limitante = next((i.insumo.nombre for i in ingredientes if i.insumo_id == limitante), None)

    filas = []
    for ing in ingredientes:
        fila = {
            'insumo': ing.insumo_id,
            'insumo_nombre': ing.insumo.nombre,
            'tipo_medida': ing.insumo.tipo_medida,
            'cantidad': ing.cantidad,
            'cantidad_texto': texto_cantidad(ing.cantidad, ing.insumo.tipo_medida),
        }
        if ve_costos:
            costo = costos.get(ing.insumo_id)
            fila['costo'] = redondear_dinero(ing.cantidad * costo) if costo and costo > 0 else None
        filas.append(fila)

    productos = []
    costo_plato, completo = costo_de_receta([(i.cantidad, costos.get(i.insumo_id)) for i in ingredientes]) if ve_costos else (None, None)
    for p in sorted(receta.productos.all(), key=lambda p: p.nombre.lower()):
        item = {'id': p.id, 'nombre': p.nombre, 'activo': p.activo}
        if ve_costos:
            item['precio'] = p.precio_actual
            if completo and p.precio_actual > 0:
                item['margen'] = redondear_dinero(p.precio_actual - costo_plato)
                item['margen_pct'] = redondear_dinero((p.precio_actual - costo_plato) * 100 / p.precio_actual)
            else:
                item['margen'] = item['margen_pct'] = None
        productos.append(item)

    salida = {
        'id': receta.id,
        'nombre': receta.nombre,
        'descripcion': receta.descripcion,
        'ingredientes': filas,
        'productos': productos,
        'porciones_posibles': posibles,
        'insumo_limitante': nombre_limitante,
    }
    if ve_costos:
        salida['costo'] = costo_plato                 # lo que cuesta preparar UNA unidad, a costo de reposicion
        salida['costo_completo'] = completo           # False: algun insumo todavia no tiene costo (nunca se compro)
    return salida


def contexto_lectura(recetas, ve_costos):
    """Stock disponible y costos de reposicion de todos los insumos de las recetas dadas (pocas consultas)."""
    ids = {i.insumo_id for r in recetas for i in r.ingredientes.all()}
    disponible = stock_disponible(ids)
    costos = {i: ultimo_costo(i) for i in ids} if ve_costos else {}
    return disponible, costos
