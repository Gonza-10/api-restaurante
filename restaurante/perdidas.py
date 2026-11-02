"""Perdidas con motivo (hito 4): registro y lectura.

Dos casos:
- Perdida de un INSUMO (se vencio, se derramo, se rompio): sale del stock, por FEFO, la cantidad indicada.
- Perdida de un PLATO ya cocinado (se cayo, se quemo, volvio de la mesa): salen del stock los insumos de su receta,
  por cada unidad perdida, tambien por FEFO.

En los dos casos se guarda UNA fila en Perdida (que, cuanto, por que, quien) y cada movimiento del libro queda enlazado
a ella. El valor no se guarda: se calcula con el costo real de los lotes de donde salio cada cantidad, asi nunca hay un
promedio general. Todo o nada: si el stock registrado no alcanza, no se modifica nada.
"""
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Insumo, MovimientoStock, Perdida, RecetaIngrediente
from .recetas import recalcular_al_confirmar
from .serializers import fecha_iso
from .stock import _id_jornada_actual, descontar_fefo
from .stock_calculos import (
    ETIQUETA_MOTIVO, MOTIVO_VENCIMIENTO, UNIDAD_BASE, redondear_dinero, texto_cantidad, valorizar_tomas,
)


class ProductoSinReceta(Exception):
    """El plato no tiene receta: no hay insumos que descontar."""


def _tipo_de_movimiento(motivo):
    return 'Vencido' if motivo == MOTIVO_VENCIMIENTO else 'Perdida'


def registrar_perdida_insumo(insumo, cantidad, motivo, nota, empleado):
    """Registra la perdida de `cantidad` (unidad base) de un insumo. Lanza StockInsuficiente (sin modificar nada) si
    el stock registrado no alcanza."""
    with transaction.atomic():
        perdida = Perdida.objects.create(
            fecha_hora=timezone.now(), empleado=empleado, jornada_id=_id_jornada_actual(), alcance='Insumo',
            insumo=insumo, cantidad=cantidad, motivo=motivo, nota=nota,
        )
        descontar_fefo(
            insumo, cantidad, _tipo_de_movimiento(motivo), empleado=empleado, id_jornada=perdida.jornada_id,
            motivo=ETIQUETA_MOTIVO[motivo], nota=nota, id_perdida=perdida.id,
        )
        recalcular_al_confirmar(ids_insumo=[insumo.id])
        return perdida


def registrar_perdida_plato(producto, unidades, motivo, nota, empleado):
    """Registra la perdida de `unidades` (enteras) de un plato: descuenta de cada insumo de su receta
    cantidad x unidades. Lanza ProductoSinReceta si el producto no tiene receta, y StockInsuficiente (sin modificar
    nada) si algun insumo no alcanza."""
    if producto.receta_id is None:
        raise ProductoSinReceta(f'{producto.nombre} no tiene receta: no hay insumos que descontar.')
    ingredientes = list(RecetaIngrediente.objects.filter(receta_id=producto.receta_id).order_by('insumo_id'))
    if not ingredientes:
        raise ProductoSinReceta(f'La receta de {producto.nombre} no tiene ingredientes.')
    unidades = Decimal(unidades)
    insumos = Insumo.objects.in_bulk([i.insumo_id for i in ingredientes])
    with transaction.atomic():
        perdida = Perdida.objects.create(
            fecha_hora=timezone.now(), empleado=empleado, jornada_id=_id_jornada_actual(), alcance='Plato',
            producto=producto, cantidad=unidades, motivo=motivo, nota=nota,
        )
        # siempre en el mismo orden (por id de insumo): evita bloqueos cruzados con el worker y con otras perdidas
        for ingrediente in ingredientes:
            descontar_fefo(
                insumos[ingrediente.insumo_id], ingrediente.cantidad * unidades, _tipo_de_movimiento(motivo),
                empleado=empleado, id_jornada=perdida.jornada_id, motivo=ETIQUETA_MOTIVO[motivo], nota=nota,
                id_perdida=perdida.id,
            )
        recalcular_al_confirmar(ids_insumo=[i.insumo_id for i in ingredientes])
        return perdida


# ---------- lectura ----------

def consumos_por_perdida(ids_perdida):
    """{id_perdida: [{'insumo', 'insumo_nombre', 'tipo_medida', 'lote', 'cantidad', 'costo_unitario'}, ...]}
    con lo que salio de cada lote (cantidad positiva) y el costo por unidad base de ese lote."""
    resultado = defaultdict(list)
    ids_perdida = list(ids_perdida)
    if not ids_perdida:
        return resultado
    filas = (
        MovimientoStock.objects.filter(perdida_id__in=ids_perdida)
        .values_list(
            'perdida_id', 'lote_id', 'cantidad', 'lote__costo_unitario', 'lote__insumo_id', 'lote__insumo__nombre',
            'lote__insumo__tipo_medida',
        )
        .order_by('id')
    )
    for id_perdida, id_lote, cantidad, costo, id_insumo, nombre, tipo_medida in filas:
        resultado[id_perdida].append({
            'insumo': id_insumo, 'insumo_nombre': nombre, 'tipo_medida': tipo_medida, 'lote': id_lote,
            'cantidad': -cantidad, 'costo_unitario': costo,
        })
    return resultado


def valor_de_perdida(consumos):
    """(valor, completo) de una perdida, a costo real de los lotes tocados."""
    return valorizar_tomas([(c['cantidad'], c['costo_unitario']) for c in consumos])


def armar_perdida(perdida, consumos, ve_costos, detalle=False):
    """Representacion de una perdida. Cocina ve que se perdio, cuanto, el motivo y quien lo cargo; el valor (y el
    costo de cada lote) solo lo ven Admin y Gerente. `detalle` agrega de que insumos y lotes salio."""
    es_insumo = perdida.alcance == 'Insumo'
    if es_insumo:
        nombre = perdida.insumo.nombre
        cantidad_texto = texto_cantidad(perdida.cantidad, perdida.insumo.tipo_medida)
        unidad = UNIDAD_BASE[perdida.insumo.tipo_medida]
    else:
        nombre = perdida.producto.nombre
        cantidad_texto = f'{int(perdida.cantidad)} u'
        unidad = 'u'
    empleado = perdida.empleado
    datos = {
        'id': perdida.id,
        'fecha_hora': fecha_iso(perdida.fecha_hora),
        'tipo': 'insumo' if es_insumo else 'plato',
        'insumo': perdida.insumo_id,
        'producto': perdida.producto_id,
        'nombre': nombre,
        'cantidad': perdida.cantidad,
        'unidad': unidad,
        'cantidad_texto': cantidad_texto,
        'motivo': perdida.motivo,
        'motivo_etiqueta': ETIQUETA_MOTIVO.get(perdida.motivo, perdida.motivo),
        'nota': perdida.nota,
        'registrado_por': f'{empleado.nombre} {empleado.apellido}',
        'jornada': perdida.jornada_id,
    }
    if ve_costos:
        valor, completo = valor_de_perdida(consumos)
        datos['valor'] = valor
        datos['valor_completo'] = completo
    if detalle:
        filas = []
        for c in consumos:
            fila = {
                'insumo': c['insumo'],
                'insumo_nombre': c['insumo_nombre'],
                'lote': c['lote'],
                'cantidad': c['cantidad'],
                'cantidad_texto': texto_cantidad(c['cantidad'], c['tipo_medida']),
            }
            if ve_costos:
                fila['costo_unitario'] = c['costo_unitario']
                fila['valor'] = redondear_dinero(c['cantidad'] * c['costo_unitario'])
            filas.append(fila)
        datos['consumos'] = filas
    return datos
