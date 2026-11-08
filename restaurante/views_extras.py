"""Vistas de los extras por receta (cobros, hito 5). Ver extras.py para las reglas.

GET  /recetas/<id>/extras          Cocina, Admin, Gerente (Cocina solo lee)
POST /recetas/<id>/extras          Admin, Gerente: agrega un extra a la receta
POST /recetas/<id>/extras/copiar   Admin, Gerente: copia los extras de otra receta (sin pisar los que ya tiene)
GET  /extras/<id>                  Cocina, Admin, Gerente
PUT/PATCH /extras/<id>             Admin, Gerente: cambia cantidad, precio, maximo o activo (el insumo no se cambia: se crea otro)
DELETE /extras/<id>                Admin, Gerente: lo borra si nunca se uso en un pedido; si no, 409 (desactivarlo con activo=false)
"""
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, COCINA
from .catalogo import invalidar_cache_catalogo
from .extras import copiar_extras
from .models import PedidoDetalleExtra, Receta, RecetaExtra
from .recetas import calcular_disponibilidad_extras, recalcular_al_confirmar
from .serializers_recetas import ExtraCopiarSerializer, ExtraEntradaSerializer
from .stock_calculos import texto_cantidad


def _extra_json(extra):
    return {
        'id': extra.id,
        'receta': extra.receta_id,
        'insumo': extra.insumo_id,
        'insumo_nombre': extra.insumo.nombre,
        'tipo_medida': extra.insumo.tipo_medida,
        'cantidad': str(extra.cantidad),
        'cantidad_texto': texto_cantidad(extra.cantidad, extra.insumo.tipo_medida),
        'precio': str(extra.precio),
        'max_por_unidad': extra.max_por_unidad,
        'activo': extra.activo,
        'disponible': extra.disponible,
    }


def _receta_de_plato(pk):
    return get_object_or_404(Receta.objects.filter(insumo_producido__isnull=True), pk=pk)


def _actualizar_disponibilidad(ids_extra=None, receta=None):
    """Deja RecetaExtra.disponible al dia con el stock de ahora (un extra nuevo o con otra cantidad pudo cambiar) y avisa al menu."""
    ids_producto = list(receta.productos.values_list('id', flat=True)) if receta is not None else []
    if ids_producto:
        recalcular_al_confirmar(ids_producto=ids_producto)
    else:
        invalidar_cache_catalogo()


def _fijar_disponibilidad(extras):
    """Calcula y guarda `disponible` de estos extras segun el stock de ahora (sin esperar al proximo movimiento de stock)."""
    ids = [e.id for e in extras]
    nuevos = {i: nuevo for i, _, nuevo in calcular_disponibilidad_extras(ids_insumo=[e.insumo_id for e in extras]) if i in ids}
    for extra in extras:
        if extra.id in nuevos and nuevos[extra.id] != extra.disponible:
            RecetaExtra.objects.filter(pk=extra.pk).update(disponible=nuevos[extra.id])
            extra.disponible = nuevos[extra.id]


class RecetaExtrasView(APIView):
    roles_lectura = COCINA
    roles_escritura = ADMIN_GERENTE

    def get(self, request, pk):
        receta = _receta_de_plato(pk)
        extras = receta.extras.select_related('insumo').order_by('insumo__nombre')
        return Response([_extra_json(e) for e in extras])

    def post(self, request, pk):
        receta = _receta_de_plato(pk)
        entrada = ExtraEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        if receta.extras.filter(insumo=datos['insumo']).exists():
            raise ValidationError({'insumo': 'Esa receta ya ofrece ese insumo como extra: editar el existente.'})
        try:
            with transaction.atomic():
                extra = RecetaExtra.objects.create(
                    receta=receta, insumo=datos['insumo'], cantidad=datos['cantidad'], precio=datos['precio'],
                    max_por_unidad=datos['max_por_unidad'], activo=datos['activo'],
                )
        except IntegrityError:   # dos altas a la vez del mismo insumo
            raise ValidationError({'insumo': 'Esa receta ya ofrece ese insumo como extra: editar el existente.'})
        _fijar_disponibilidad([extra])
        invalidar_cache_catalogo()
        extra = RecetaExtra.objects.select_related('insumo').get(pk=extra.pk)
        return Response(_extra_json(extra), status=status.HTTP_201_CREATED)


class RecetaExtrasCopiarView(APIView):
    roles_escritura = ADMIN_GERENTE

    def post(self, request, pk):
        destino = _receta_de_plato(pk)
        entrada = ExtraCopiarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        origen = entrada.validated_data['origen']
        if origen.pk == destino.pk:
            raise ValidationError({'origen': 'Elegi otra receta: no se pueden copiar los extras de una receta a si misma.'})
        copiados, omitidos = copiar_extras(origen, destino)
        if copiados:
            _fijar_disponibilidad(list(destino.extras.select_related('insumo')))
            invalidar_cache_catalogo()
        extras = destino.extras.select_related('insumo').order_by('insumo__nombre')
        return Response(
            {'copiados': copiados, 'omitidos_por_existir': omitidos, 'extras': [_extra_json(e) for e in extras]},
            status=status.HTTP_201_CREATED if copiados else status.HTTP_200_OK,
        )


class ExtraDetalleView(APIView):
    roles_lectura = COCINA
    roles_escritura = ADMIN_GERENTE

    @staticmethod
    def _extra(pk):
        return get_object_or_404(RecetaExtra.objects.select_related('insumo', 'receta'), pk=pk)

    def get(self, request, pk):
        return Response(_extra_json(self._extra(pk)))

    def _guardar(self, request, pk, parcial):
        extra = self._extra(pk)
        actual = {'insumo': extra.insumo_id, 'cantidad': extra.cantidad, 'precio': extra.precio,
                  'max_por_unidad': extra.max_por_unidad, 'activo': extra.activo}
        datos_in = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if parcial:   # PATCH: lo que no se manda queda como esta
            for campo, valor in actual.items():
                datos_in.setdefault(campo, valor)
        entrada = ExtraEntradaSerializer(data=datos_in)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        if datos['insumo'].id != extra.insumo_id:
            raise ValidationError({'insumo': 'El insumo de un extra no se cambia: desactivarlo y crear otro.'})
        extra.cantidad, extra.precio = datos['cantidad'], datos['precio']
        extra.max_por_unidad, extra.activo = datos['max_por_unidad'], datos['activo']
        extra.save(update_fields=['cantidad', 'precio', 'max_por_unidad', 'activo'])
        _fijar_disponibilidad([extra])
        invalidar_cache_catalogo()   # el menu del cliente muestra el precio, el maximo y si se ofrece
        return Response(_extra_json(self._extra(pk)))

    def put(self, request, pk):
        return self._guardar(request, pk, parcial=False)

    def patch(self, request, pk):
        return self._guardar(request, pk, parcial=True)

    def delete(self, request, pk):
        extra = self._extra(pk)
        if PedidoDetalleExtra.objects.filter(extra=extra).exists():
            return Response(
                {'error': 'Ese extra ya se uso en pedidos: no se borra para no perder el historial. Desactivalo con activo=false.'},
                status=status.HTTP_409_CONFLICT,
            )
        extra.delete()
        invalidar_cache_catalogo()
        return Response(status=status.HTTP_204_NO_CONTENT)
