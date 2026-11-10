"""Elaboraciones (hito 6): insumos que la cocina produce a partir de otros (salsa, masa, caldo).

Una elaboracion es una receta con `insumo_producido` y `rinde`: cuanto sale de UNA tanda. Al registrar una produccion:
- se descuentan los ingredientes por FEFO (y pueden ser, a su vez, otras elaboraciones ya producidas);
- entra un lote nuevo del insumo producido, de origen 'Elaboracion', con costo REAL: lo que costaron los lotes consumidos
  dividido lo que salio (nunca un promedio general);
- todo queda en el libro de movimientos, enlazado a la Produccion.
Todo o nada: si no alcanza algun ingrediente no se modifica nada. Los calculos puros estan en stock_calculos.py.
"""
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import LoteInsumo, MovimientoStock, Produccion, RecetaIngrediente
from .recetas import recalcular_al_confirmar
from .serializers import fecha_iso
from .stock import _id_jornada_actual, descontar_fefo
from .stock_calculos import (
    CERO, PASO_COSTO, UNIDAD_BASE, calcular_produccion, costo_unitario_producido, porciones_posibles, redondear_dinero,
    texto_cantidad, valorizar_tomas,
)


class ProduccionInvalida(Exception):
    """Las tandas pedidas no dan cantidades validas (por ejemplo, medio huevo). Lleva la lista de errores."""

    def __init__(self, errores):
        super().__init__('Produccion invalida.')
        self.errores = errores


class InsumoProducidoInactivo(Exception):
    """El insumo que sale de la elaboracion esta dado de baja."""


def dependencias(excluir_receta_id=None):
    """{id_insumo_producido: [ids de sus ingredientes]} de todas las elaboraciones (menos `excluir_receta_id`):
    el grafo para detectar ciclos."""
    consulta = RecetaIngrediente.objects.filter(receta__insumo_producido__isnull=False)
    if excluir_receta_id is not None:
        consulta = consulta.exclude(receta_id=excluir_receta_id)
    grafo = defaultdict(list)
    for id_producido, id_ingrediente in consulta.values_list('receta__insumo_producido_id', 'insumo_id'):
        grafo[id_producido].append(id_ingrediente)
    return dict(grafo)


def registrar_produccion(receta, tandas, empleado, nota=None, fecha_vencimiento=None):
    """Elabora `tandas` tandas de una receta de elaboracion. Lanza ProduccionInvalida (cantidades que no dan),
    InsumoProducidoInactivo o StockInsuficiente (sin modificar nada) si no alcanza algun ingrediente."""
    producido = receta.insumo_producido
    if not producido.activo:
        raise InsumoProducidoInactivo(f'{producido.nombre} esta dado de baja.')
    ingredientes = list(RecetaIngrediente.objects.filter(receta_id=receta.id).select_related('insumo').order_by('insumo_id'))
    calculo = calcular_produccion(
        [(i.insumo_id, i.cantidad, i.insumo.tipo_medida, i.insumo.nombre) for i in ingredientes],
        receta.rinde, tandas, producido.tipo_medida,
    )
    if calculo['errores']:
        raise ProduccionInvalida(calculo['errores'])
    cantidad = calculo['cantidad']
    insumos = {i.insumo_id: i.insumo for i in ingredientes}
    with transaction.atomic():
        ahora = timezone.now()
        id_jornada = _id_jornada_actual()
        produccion = Produccion.objects.create(
            fecha_hora=ahora, empleado=empleado, jornada_id=id_jornada, receta=receta, insumo=producido,
            tandas=tandas, cantidad=cantidad, nota=nota,
        )
        tomas = []
        # siempre en el mismo orden (por id de insumo): evita bloqueos cruzados con el worker y con otras producciones
        for id_insumo, necesario in calculo['necesario']:
            movimientos = descontar_fefo(
                insumos[id_insumo], necesario, 'Consumo', empleado=empleado, id_jornada=id_jornada,
                motivo=f'Elaboracion de {producido.nombre}', nota=nota, id_produccion=produccion.id,
            )
            tomas.extend((m.cantidad, m.lote.costo_unitario) for m in movimientos)
        costo, _ = costo_unitario_producido(tomas, cantidad)
        if fecha_vencimiento is None and receta.dias_vencimiento:
            fecha_vencimiento = timezone.localdate() + timedelta(days=receta.dias_vencimiento)
        lote = LoteInsumo.objects.create(
            insumo=producido, compra=None, origen='Elaboracion', fecha_ingreso=ahora, fecha_vencimiento=fecha_vencimiento,
            cantidad_inicial=cantidad, cantidad_actual=cantidad, costo_unitario=costo, estado='Activo',
        )
        MovimientoStock.objects.create(
            lote=lote, tipo='Elaboracion', cantidad=cantidad, fecha_hora=ahora, empleado=empleado, jornada_id=id_jornada,
            produccion_id=produccion.id, motivo=f'Elaboracion de {producido.nombre}', nota=nota,
        )
        # los ingredientes bajaron (puede haber platos que dejan de alcanzar) y el producido subio (pueden volver)
        recalcular_al_confirmar(ids_insumo=[id_insumo for id_insumo, _ in calculo['necesario']] + [producido.id])
        return produccion


# ---------- lectura ----------

def armar_elaboracion(receta, ve_costos, disponible, costos):
    """Representacion de una elaboracion. `disponible` = {id_insumo: stock}, `costos` = {id_insumo: costo de reposicion}.
    Cocina ve cantidades y cuantas tandas puede hacer; los costos solo los ven Admin y Gerente."""
    ingredientes = sorted(receta.ingredientes.all(), key=lambda i: i.insumo.nombre.lower())
    pares = [(i.insumo_id, i.cantidad) for i in ingredientes]
    tandas, limitante = porciones_posibles(pares, disponible)
    nombre_limitante = next((i.insumo.nombre for i in ingredientes if i.insumo_id == limitante), None)
    producido = receta.insumo_producido
    filas = []
    costo_tanda = CERO
    completo = True
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
            if costo and costo > 0:
                fila['costo'] = redondear_dinero(ing.cantidad * costo)
                costo_tanda += ing.cantidad * costo
            else:
                fila['costo'] = None
                completo = False
        filas.append(fila)
    salida = {
        'id': receta.id,
        'nombre': receta.nombre,
        'descripcion': receta.descripcion,
        'insumo': producido.id,
        'insumo_nombre': producido.nombre,
        'tipo_medida': producido.tipo_medida,
        'unidad': UNIDAD_BASE[producido.tipo_medida],
        'rinde': receta.rinde,
        'rinde_texto': texto_cantidad(receta.rinde, producido.tipo_medida),
        'dias_vencimiento': receta.dias_vencimiento,
        'ingredientes': filas,
        'tandas_posibles': tandas,
        'insumo_limitante': nombre_limitante,
    }
    if ve_costos:
        salida['costo_tanda'] = redondear_dinero(costo_tanda)           # a costo de reposicion
        salida['costo_por_unidad_base'] = (costo_tanda / receta.rinde).quantize(PASO_COSTO) if completo else None
        salida['costo_completo'] = completo
    return salida


def armar_producciones(producciones, ve_costos, detalle=False):
    """Representaciones de producciones. El costo sale del libro: lo que valian los lotes consumidos."""
    producciones = list(producciones)
    ids = [p.id for p in producciones]
    consumos = defaultdict(list)
    ingresos = {}
    if ids:
        movimientos = (
            MovimientoStock.objects.filter(produccion_id__in=ids).select_related('lote__insumo').order_by('id')
        )
        for m in movimientos:
            if m.tipo == 'Elaboracion':
                ingresos[m.produccion_id] = m
            else:
                consumos[m.produccion_id].append(m)
    salida = []
    for p in producciones:
        ingreso = ingresos.get(p.id)
        empleado = p.empleado
        dato = {
            'id': p.id,
            'fecha_hora': fecha_iso(p.fecha_hora),
            'elaboracion': p.receta_id,
            'insumo': p.insumo_id,
            'insumo_nombre': p.insumo.nombre,
            'tandas': p.tandas,
            'cantidad': p.cantidad,
            'cantidad_texto': texto_cantidad(p.cantidad, p.insumo.tipo_medida),
            'nota': p.nota,
            'registrado_por': f'{empleado.nombre} {empleado.apellido}',
            'jornada': p.jornada_id,
            'lote': ingreso.lote_id if ingreso else None,
            'fecha_vencimiento': ingreso.lote.fecha_vencimiento if ingreso else None,
        }
        if ve_costos:
            valor, completo = valorizar_tomas([(m.cantidad, m.lote.costo_unitario) for m in consumos.get(p.id, [])])
            dato['costo_total'] = valor
            dato['costo_por_unidad_base'] = ingreso.lote.costo_unitario if ingreso else None
            dato['costo_completo'] = completo
        if detalle:
            filas = []
            for m in consumos.get(p.id, []):
                fila = {
                    'insumo': m.lote.insumo_id,
                    'insumo_nombre': m.lote.insumo.nombre,
                    'lote': m.lote_id,
                    'cantidad': -m.cantidad,
                    'cantidad_texto': texto_cantidad(-m.cantidad, m.lote.insumo.tipo_medida),
                }
                if ve_costos:
                    fila['costo_unitario'] = m.lote.costo_unitario
                    fila['valor'] = redondear_dinero(-m.cantidad * m.lote.costo_unitario)
                filas.append(fila)
            dato['consumos'] = filas
        salida.append(dato)
    return salida
