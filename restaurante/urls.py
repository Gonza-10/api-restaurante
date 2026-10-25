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
    SolicitarCuentaView,
    HistorialMesaView,
)
from .views_disponibilidad import catalogo_eventos, CatalogoVersionView, ProductoDisponibilidadView
from .views_operacion import (
    TurnoViewSet,
    JornadaViewSet,
    JornadaActualView,
    JornadaAbrirView,
    JornadaCerrarView,
    EspecialViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register(r'categorias', CategoriaViewSet)
router.register(r'productos', ProductoViewSet, basename='producto')
router.register(r'mesas', MesaViewSet, basename='mesa')
router.register(r'roles', RolViewSet, basename='rol')
router.register(r'empleados', EmpleadoViewSet, basename='empleado')
router.register(r'sesiones-mesa', PedidoCabeceraViewSet, basename='sesion-mesa')
router.register(r'detalles-pedido', PedidoDetalleViewSet)
router.register(r'turnos', TurnoViewSet, basename='turno')
router.register(r'jornadas', JornadaViewSet, basename='jornada')
router.register(r'especiales', EspecialViewSet, basename='especial')

urlpatterns = [
    path('', include(router.urls)),
    path('login', LoginView.as_view(), name='login'),
    path('me', PerfilView.as_view(), name='perfil'),
    path('acceso-mesa', AccesoMesaView.as_view(), name='acceso-mesa'),
    path('jornada/actual', JornadaActualView.as_view(), name='jornada-actual'),
    path('jornada/abrir', JornadaAbrirView.as_view(), name='jornada-abrir'),
    path('jornada/cerrar', JornadaCerrarView.as_view(), name='jornada-cerrar'),
    path('catalogo/eventos', catalogo_eventos, name='catalogo-eventos'),
    path('catalogo/version', CatalogoVersionView.as_view(), name='catalogo-version'),
    path('productos/<int:pk>/agotar', ProductoDisponibilidadView.as_view(accion='agotar'), name='producto-agotar'),
    path('productos/<int:pk>/reactivar', ProductoDisponibilidadView.as_view(accion='reactivar'), name='producto-reactivar'),
    path('solicitar-cuenta', SolicitarCuentaView.as_view(), name='solicitar-cuenta'),
    path('mesa/historial', HistorialMesaView.as_view(), name='historial-mesa'),
    path('pedidos', ComandaCreateView.as_view(), name='crear-comanda'),
    path('pedidos/<uuid:uuid_comanda>/estado', ComandaEstadoUpdateView.as_view(), name='actualizar-estado-comanda'),
    path('cocina/tablero', TableroCocinaView.as_view(), name='tablero-cocina'),
    path('pedidos/<uuid:uuid_comanda>/ticket', TicketPDFView.as_view(), name='ticket-comanda'),
    path('tickets/<uuid:uuid_comanda>.pdf', TicketPDFView.as_view(), name='ticket-comanda-pdf'),  # ruta que usa el front
]