from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaViewSet,
    ProductoViewSet,
    MesaViewSet,
    EmpleadoViewSet,
    RolViewSet,
    PedidoCabeceraViewSet,
    PedidoDetalleViewSet,
    ComandaCreateView,
    TableroCocinaView,
    ComandaEstadoUpdateView,
    TicketPDFView,
    LoginView,
    PerfilView,
    AccesoMesaView,
)

router = DefaultRouter(trailing_slash=False)
router.register(r'categorias', CategoriaViewSet)
router.register(r'productos', ProductoViewSet, basename='producto')
router.register(r'mesas', MesaViewSet, basename='mesa')
router.register(r'roles', RolViewSet, basename='rol')
router.register(r'empleados', EmpleadoViewSet, basename='empleado')
router.register(r'sesiones-mesa', PedidoCabeceraViewSet, basename='sesion-mesa')
router.register(r'detalles-pedido', PedidoDetalleViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('login', LoginView.as_view(), name='login'),
    path('me', PerfilView.as_view(), name='perfil'),
    path('acceso-mesa', AccesoMesaView.as_view(), name='acceso-mesa'),
    path('pedidos', ComandaCreateView.as_view(), name='crear-comanda'),
    path('pedidos/<uuid:uuid_comanda>/estado', ComandaEstadoUpdateView.as_view(), name='actualizar-estado-comanda'),
    path('cocina/tablero', TableroCocinaView.as_view(), name='tablero-cocina'),
    path('pedidos/<uuid:uuid_comanda>/ticket', TicketPDFView.as_view(), name='ticket-comanda'),
]