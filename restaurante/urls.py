from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaViewSet,
    ProductoViewSet,
    MesaViewSet,
    EmpleadoViewSet,
    PedidoCabeceraViewSet,
    PedidoDetalleViewSet,
    ComandaCreateView,
    TableroCocinaView,
    ComandaEstadoUpdateView,
)

router = DefaultRouter(trailing_slash=False)
router.register(r'categorias', CategoriaViewSet)
router.register(r'productos', ProductoViewSet, basename='producto')
router.register(r'mesas', MesaViewSet)
router.register(r'empleados', EmpleadoViewSet)
router.register(r'sesiones-mesa', PedidoCabeceraViewSet)
router.register(r'detalles-pedido', PedidoDetalleViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('pedidos', ComandaCreateView.as_view(), name='crear-comanda'),
    path('pedidos/<uuid:uuid_comanda>/estado', ComandaEstadoUpdateView.as_view(), name='actualizar-estado-comanda'),
    path('cocina/tablero', TableroCocinaView.as_view(), name='tablero-cocina'),
]