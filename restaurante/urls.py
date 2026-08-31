from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaViewSet,
    ProductoViewSet,
    MesaViewSet,
    EmpleadoViewSet,
    PedidoCabeceraViewSet,
    PedidoDetalleViewSet,
)

router = DefaultRouter()
router.register(r'categorias', CategoriaViewSet)
router.register(r'productos', ProductoViewSet, basename='producto')
router.register(r'mesas', MesaViewSet)
router.register(r'empleados', EmpleadoViewSet)
router.register(r'pedidos', PedidoCabeceraViewSet)
router.register(r'detalles-pedido', PedidoDetalleViewSet)

urlpatterns = [
    path('', include(router.urls)),
]