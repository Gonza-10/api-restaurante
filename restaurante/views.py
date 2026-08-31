from rest_framework import viewsets

from .models import Categoria, Producto, Mesa, Empleado, PedidoCabecera, PedidoDetalle
from .serializers import (
    CategoriaSerializer,
    ProductoSerializer,
    MesaSerializer,
    EmpleadoSerializer,
    PedidoCabeceraSerializer,
    PedidoDetalleSerializer,
)


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer


class ProductoViewSet(viewsets.ModelViewSet):
    serializer_class = ProductoSerializer

    def get_queryset(self):
        queryset = Producto.objects.select_related('categoria').all()
        if self.action == 'list':
            categoria_id = self.request.query_params.get('categoria')
            vegetariano = self.request.query_params.get('vegetariano')
            celiaco = self.request.query_params.get('celiaco')
            if categoria_id:
                queryset = queryset.filter(categoria_id=categoria_id)
            if vegetariano == 'true':
                queryset = queryset.filter(es_vegetariano=True)
            if celiaco == 'true':
                queryset = queryset.filter(apto_celiaco=True)
        return queryset


class MesaViewSet(viewsets.ModelViewSet):
    queryset = Mesa.objects.all()
    serializer_class = MesaSerializer


class EmpleadoViewSet(viewsets.ModelViewSet):
    queryset = Empleado.objects.select_related('rol').all()
    serializer_class = EmpleadoSerializer


class PedidoCabeceraViewSet(viewsets.ModelViewSet):
    queryset = PedidoCabecera.objects.select_related('mesa', 'empleado').prefetch_related('detalles__producto').all()
    serializer_class = PedidoCabeceraSerializer


class PedidoDetalleViewSet(viewsets.ModelViewSet):
    queryset = PedidoDetalle.objects.select_related('producto', 'pedido_cabecera').all()
    serializer_class = PedidoDetalleSerializer