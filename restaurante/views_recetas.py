"""Vistas de las recetas (hito 2): recetas, productos sin receta y comandas rechazadas por falta de stock."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ADMIN_GERENTE, COCINA
from .models import ComandaRecibida, Producto, Receta, RecetaIngrediente
from .recetas import armar_receta, contexto_lectura
from .serializers_recetas import RecetaEntradaSerializer
from .views_operacion import _parsear_fecha


def _guardar_ingredientes(receta, ingredientes):
    receta.ingredientes.all().delete()
    RecetaIngrediente.objects.bulk_create([
        RecetaIngrediente(receta=receta, insumo=i['insumo'], cantidad=i['cantidad']) for i in ingredientes
    ])


class RecetaViewSet(viewsets.ModelViewSet):
    """Recetas: que insumos gasta UNA unidad vendida (cantidades en unidad base: g, ml o u).
    Lectura: Cocina, Admin y Gerente (Cocina ve cantidades y cuantas unidades se pueden preparar, sin costos).
    Escritura: Admin y Gerente. En el PUT, `ingredientes` reemplaza la lista completa.
    Una receta se asigna a uno o varios productos con PUT /productos/<id>/receta {"receta": <id>} (null = sin control de stock).
    DELETE solo si ningun producto la usa. Filtro: ?buscar=texto."""
    roles_lectura = COCINA
    roles_escritura = ADMIN_GERENTE

    def get_queryset(self):
        consulta = Receta.objects.prefetch_related('ingredientes__insumo', 'productos').order_by('nombre')
        if self.action == 'list':
            texto = (self.request.query_params.get('buscar') or '').strip()
            if texto:
                consulta = consulta.filter(nombre__icontains=texto)
        return consulta

    def _salida(self, recetas, ve_costos):
        recetas = list(recetas)
        disponible, costos = contexto_lectura(recetas, ve_costos)
        return [armar_receta(r, ve_costos, disponible, costos) for r in recetas]

    def _ve_costos(self, request):
        return request.user.rol in ADMIN_GERENTE

    def list(self, request, *args, **kwargs):
        return Response(self._salida(self.get_queryset(), self._ve_costos(request)))

    def retrieve(self, request, *args, **kwargs):
        return Response(self._salida([self.get_object()], self._ve_costos(request))[0])

    def create(self, request, *args, **kwargs):
        entrada = RecetaEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        with transaction.atomic():
            receta = Receta.objects.create(nombre=datos['nombre'], descripcion=datos.get('descripcion') or None)
            _guardar_ingredientes(receta, datos['ingredientes'])
        receta = self.get_queryset().get(pk=receta.pk)
        return Response(self._salida([receta], True)[0], status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        receta = self.get_object()
        entrada = RecetaEntradaSerializer(receta, data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        with transaction.atomic():
            receta.nombre = datos['nombre']
            receta.descripcion = datos.get('descripcion') or None
            receta.save(update_fields=['nombre', 'descripcion'])
            _guardar_ingredientes(receta, datos['ingredientes'])
        receta = self.get_queryset().get(pk=receta.pk)
        return Response(self._salida([receta], True)[0])

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {'error': 'Use PUT con la receta completa (nombre e ingredientes).'}, status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def destroy(self, request, *args, **kwargs):
        receta = self.get_object()
        usados = list(receta.productos.values_list('nombre', flat=True)[:5])
        if usados:
            return Response(
                {'error': 'La receta la usan estos productos: ' + ', '.join(usados)
                          + '. Desasignarla de cada uno antes de borrarla.'},
                status=status.HTTP_409_CONFLICT
            )
        receta.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductoRecetaView(APIView):
    """GET/PUT /productos/<id>/receta. Que receta gasta este producto (null = sin control de stock).
    PUT {"receta": <id de la receta> | null}. Lectura: Cocina, Admin y Gerente. Escritura: Admin y Gerente.
    No se mezcla con PUT /productos/<id> porque el menu es publico y la receta es interna."""
    roles_lectura = COCINA
    roles_escritura = ADMIN_GERENTE

    @staticmethod
    def _salida(producto):
        receta = producto.receta
        return {
            'id': producto.id, 'nombre': producto.nombre,
            'receta': receta.id if receta else None, 'receta_nombre': receta.nombre if receta else None,
        }

    def get(self, request, pk):
        producto = get_object_or_404(Producto.objects.select_related('receta'), pk=pk)
        return Response(self._salida(producto))

    def put(self, request, pk):
        producto = get_object_or_404(Producto.objects.select_related('receta'), pk=pk)
        if 'receta' not in request.data:
            raise ValidationError({'receta': 'Campo obligatorio (el id de la receta, o null para quitarla).'})
        valor = request.data['receta']
        if valor is None:
            producto.receta = None
        else:
            try:
                producto.receta = Receta.objects.get(pk=int(valor))
            except (TypeError, ValueError):
                raise ValidationError({'receta': 'Debe ser el id de la receta o null.'})
            except Receta.DoesNotExist:
                raise ValidationError({'receta': 'No existe una receta con ese id.'})
        producto.save(update_fields=['receta'])
        return Response(self._salida(producto))


class ProductosSinRecetaView(APIView):
    """GET /productos-sin-receta. Productos en carta sin receta (no descuentan stock). Es normal para las bebidas que se
    venden cerradas; sirve para no olvidarse de ningun plato. Admin y Gerente."""
    roles_lectura = ADMIN_GERENTE

    def get(self, request):
        productos = Producto.objects.filter(activo=True, receta__isnull=True).select_related('categoria').order_by(
            'categoria__nombre', 'nombre'
        )
        return Response([
            {'id': p.id, 'nombre': p.nombre, 'categoria': p.categoria.nombre, 'precio': p.precio_actual}
            for p in productos
        ])


class ComandasRechazadasView(APIView):
    """GET /comandas-rechazadas. Comandas que no se pudieron preparar por falta de stock, con el motivo interno
    (que plato y que insumo limito). El cliente solo ve el mensaje generico. Admin y Gerente.
    Filtros: ?desde=AAAA-MM-DD, ?hasta=AAAA-MM-DD, ?limite=N (200 por defecto)."""
    roles_lectura = ADMIN_GERENTE

    def get(self, request):
        p = request.query_params
        consulta = ComandaRecibida.objects.filter(estado='Rechazada').select_related('pedido_cabecera__mesa')
        if p.get('desde'):
            consulta = consulta.filter(fecha_hora_recepcion__date__gte=_parsear_fecha(p['desde'], 'desde'))
        if p.get('hasta'):
            consulta = consulta.filter(fecha_hora_recepcion__date__lte=_parsear_fecha(p['hasta'], 'hasta'))
        try:
            limite = min(max(int(p.get('limite', 200)), 1), 1000)
        except ValueError:
            limite = 200
        return Response([
            {
                'id_comanda_uuid': str(c.id_comanda_uuid),
                'mesa': c.pedido_cabecera.mesa.numero,
                'fecha_hora': c.fecha_hora_recepcion,
                'motivo': c.motivo,
                'mensaje_cliente': c.mensaje_cliente,
            }
            for c in consulta.order_by('-fecha_hora_recepcion', '-id')[:limite]
        ])
