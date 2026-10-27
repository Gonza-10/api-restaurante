"""Notificaciones del panel de Cocina (hito 3). No se guardan: se calculan del estado de ahora, porque todas son
situaciones (no eventos puntuales). Cuando la situacion se resuelve (Cocina reactiva el plato, se repone el insumo),
el aviso desaparece solo y no hay nada que marcar como leido."""
from django.utils import timezone

from .models import Insumo, Producto, StockInsumo
from .recetas import recetas_de_productos, stock_disponible
from .stock_calculos import (
    clave_notificacion, insumos_faltantes, porciones_posibles, resumen_notificaciones,
)


def _porcentaje_texto(valor):
    return f'{float(valor):g}'


def armar_notificaciones():
    notificaciones = []

    # --- platos con receta (solo los que estan en carta) ---
    productos = list(Producto.objects.filter(activo=True, receta__isnull=False).order_by('nombre'))
    recetas = recetas_de_productos([p.id for p in productos])
    disponible = stock_disponible({i for ingredientes in recetas.values() for i, _ in ingredientes})
    nombres_insumo = dict(Insumo.objects.filter(id__in=list(disponible)).values_list('id', 'nombre'))
    for p in productos:
        ingredientes = recetas.get(p.id)
        if not ingredientes:
            continue
        faltan = insumos_faltantes(ingredientes, disponible)
        if faltan:
            lista = [{'id': i, 'nombre': nombres_insumo.get(i)} for i in faltan]
            notificaciones.append({
                'tipo': 'plato_sin_insumos',
                'severidad': 'urgente',
                'mensaje': f"{p.nombre} no se puede preparar: faltan {', '.join(x['nombre'] for x in lista)}.",
                'producto': {'id': p.id, 'nombre': p.nombre},
                'insumos_faltantes': lista,
            })
        elif p.agotado_manual:
            # solo con receta: sin receta el sistema no sabe si volvio el stock
            posibles, _ = porciones_posibles(ingredientes, disponible)
            notificaciones.append({
                'tipo': 'se_puede_reactivar',
                'severidad': 'info',
                'mensaje': f'{p.nombre} estaba agotado y ya hay insumos para prepararlo (alcanza para {posibles}). '
                           'Se puede reactivar.',
                'producto': {'id': p.id, 'nombre': p.nombre},
                'porciones_posibles': posibles,
            })

    # --- insumos agotados o en nivel critico ---
    for f in StockInsumo.objects.filter(activo=True, estado__in=('Agotado', 'Critico')).order_by('nombre'):
        agotado = f.estado == 'Agotado'
        notificaciones.append({
            'tipo': 'insumo_critico',
            'severidad': 'urgente' if agotado else 'aviso',
            'mensaje': f'{f.nombre} esta agotado.' if agotado
            else f'{f.nombre} esta en nivel critico ({_porcentaje_texto(f.porcentaje)} %).',
            'insumo': {
                'id': f.insumo_id, 'nombre': f.nombre, 'estado': f.estado,
                'semaforo': 'rojo', 'porcentaje': float(f.porcentaje) if f.porcentaje is not None else None,
            },
        })

    notificaciones.sort(key=clave_notificacion)
    return {
        'generado': timezone.localtime().isoformat(),
        'resumen': resumen_notificaciones(notificaciones),
        'notificaciones': notificaciones,
    }
