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
    LoginView,
    PerfilView,
    AccesoMesaView,
    SolicitarCuentaView,
    HistorialMesaView,
)
from .views_stock import (
    ProveedorViewSet,
    InsumoViewSet,
    CompraViewSet,
    LoteViewSet,
    MovimientoStockViewSet,
    StockView,
    AjusteStockView,
    VerificacionLibroView,
)
from .views_elaboraciones import (
    ConfiguracionStockView,
    ElaboracionViewSet,
    ProcesarVencimientosView,
    ProduccionViewSet,
    ReposicionView,
    VencimientosView,
)
from .views_notificaciones import NotificacionesCocinaView
from .views_cobros import CotizacionesView, CotizacionesActualizarView
from .views_caja import CajaActualView, CajaAbrirView, CajaCerrarView, CajaMovimientosView, CajaViewSet
from .views_cuenta import (
    SesionCuentaView, SesionFacturaView, FacturaViewSetLista, FacturaDetalleView, PagoEfectivoView, PagoTarjetaView, PagoAnularView,
    FacturaAnularView, PropinasView, CuentaClienteView,
)
from .views_mp import (
    PagarMercadoPagoClienteView, PagarEstadoClienteView, PagarCancelarClienteView, PagoSincronizarView, PagoCancelarView,
    PagoSimularView,
)
from .views_perdidas import MotivosPerdidaView, PerdidaViewSet, ResumenPerdidasView
from .views_recetas import RecetaViewSet, ProductoRecetaView, ProductosSinRecetaView, ComandasRechazadasView
from .views_extras import RecetaExtrasView, RecetaExtrasCopiarView, ExtraDetalleView
from .views_comprobante import CuentaFacturaClienteView, CuentaComprobanteClienteView, FacturaComprobanteView
from .views_auditoria import AuditoriaView
from .views_comensales import (
    ComandaCancelarView, MesaComensalesEstadoView, MesaComensalesView, MesaOkView, MesaRegenerarPinView, SesionComensalesView,
    SesionLiberarRondaView, SesionPinVistoView, SesionRegenerarPinView,
)
from .views_reservas import (
    ReservasView, ReservaDetalleView, ReservaCancelarView, ReservasDisponibilidadView,
)
from .views_tickets import TicketPDFView
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
router.register(r'proveedores', ProveedorViewSet, basename='proveedor')
router.register(r'insumos', InsumoViewSet, basename='insumo')
router.register(r'compras', CompraViewSet, basename='compra')
router.register(r'lotes', LoteViewSet, basename='lote')
router.register(r'movimientos-stock', MovimientoStockViewSet, basename='movimiento-stock')
router.register(r'recetas', RecetaViewSet, basename='receta')
router.register(r'perdidas', PerdidaViewSet, basename='perdida')
router.register(r'elaboraciones', ElaboracionViewSet, basename='elaboracion')
router.register(r'producciones', ProduccionViewSet, basename='produccion')
router.register(r'cajas', CajaViewSet, basename='caja')

urlpatterns = [
    # van ANTES del router: si no, 'perdidas/<pk>' tomaria 'motivos' y 'resumen' como si fueran ids
    path('perdidas/motivos', MotivosPerdidaView.as_view(), name='perdidas-motivos'),
    path('perdidas/resumen', ResumenPerdidasView.as_view(), name='perdidas-resumen'),
    path('recetas/<int:pk>/extras', RecetaExtrasView.as_view(), name='receta-extras'),
    path('recetas/<int:pk>/extras/copiar', RecetaExtrasCopiarView.as_view(), name='receta-extras-copiar'),
    path('extras/<int:pk>', ExtraDetalleView.as_view(), name='extra-detalle'),
    path('facturas/<int:pk>/comprobante', FacturaComprobanteView.as_view(), name='factura-comprobante'),
    path('cuenta/factura', CuentaFacturaClienteView.as_view(), name='cuenta-factura'),
    path('cuenta/comprobante', CuentaComprobanteClienteView.as_view(), name='cuenta-comprobante'),
    path('auditoria', AuditoriaView.as_view(), name='auditoria'),
    path('reservas', ReservasView.as_view(), name='reservas'),
    path('reservas/disponibilidad', ReservasDisponibilidadView.as_view(), name='reservas-disponibilidad'),
    path('reservas/<int:pk>', ReservaDetalleView.as_view(), name='reserva-detalle'),
    path('reservas/<int:pk>/cancelar', ReservaCancelarView.as_view(), name='reserva-cancelar'),
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
    path('stock', StockView.as_view(), name='stock'),
    path('stock/ajustes', AjusteStockView.as_view(), name='stock-ajustes'),
    path('stock/verificacion', VerificacionLibroView.as_view(), name='stock-verificacion'),
    path('stock/reposicion', ReposicionView.as_view(), name='stock-reposicion'),
    path('vencimientos', VencimientosView.as_view(), name='vencimientos'),
    path('vencimientos/procesar', ProcesarVencimientosView.as_view(), name='vencimientos-procesar'),
    path('configuracion/stock', ConfiguracionStockView.as_view(), name='configuracion-stock'),
    path('productos/<int:pk>/receta', ProductoRecetaView.as_view(), name='producto-receta'),
    path('cocina/notificaciones', NotificacionesCocinaView.as_view(), name='cocina-notificaciones'),
    path('productos-sin-receta', ProductosSinRecetaView.as_view(), name='productos-sin-receta'),
    path('comandas-rechazadas', ComandasRechazadasView.as_view(), name='comandas-rechazadas'),
    path('cotizaciones', CotizacionesView.as_view(), name='cotizaciones'),
    path('cotizaciones/actualizar', CotizacionesActualizarView.as_view(), name='cotizaciones-actualizar'),
    path('caja/actual', CajaActualView.as_view(), name='caja-actual'),
    path('caja/abrir', CajaAbrirView.as_view(), name='caja-abrir'),
    path('caja/cerrar', CajaCerrarView.as_view(), name='caja-cerrar'),
    path('caja/movimientos', CajaMovimientosView.as_view(), name='caja-movimientos'),
    path('sesiones-mesa/<int:pk>/cuenta', SesionCuentaView.as_view(), name='sesion-cuenta'),
    path('sesiones-mesa/<int:pk>/factura', SesionFacturaView.as_view(), name='sesion-factura'),
    path('facturas', FacturaViewSetLista.as_view(), name='facturas'),
    path('facturas/<int:pk>', FacturaDetalleView.as_view(), name='factura-detalle'),
    path('facturas/<int:pk>/pagos/efectivo', PagoEfectivoView.as_view(), name='pago-efectivo'),
    path('facturas/<int:pk>/pagos/tarjeta', PagoTarjetaView.as_view(), name='pago-tarjeta'),
    path('facturas/<int:pk>/anular', FacturaAnularView.as_view(), name='factura-anular'),
    path('pagos/<int:pk>/anular', PagoAnularView.as_view(), name='pago-anular'),
    path('propinas', PropinasView.as_view(), name='propinas'),
    path('pagos/<int:pk>/sincronizar', PagoSincronizarView.as_view(), name='pago-sincronizar'),
    path('pagos/<int:pk>/cancelar', PagoCancelarView.as_view(), name='pago-cancelar'),
    path('pagos/<int:pk>/simular', PagoSimularView.as_view(), name='pago-simular'),
    path('cuenta', CuentaClienteView.as_view(), name='cuenta-cliente'),
    path('cuenta/pagar/mercadopago', PagarMercadoPagoClienteView.as_view(), name='cuenta-pagar-mp'),
    path('cuenta/pagar/estado', PagarEstadoClienteView.as_view(), name='cuenta-pagar-estado'),
    path('cuenta/pagar/cancelar', PagarCancelarClienteView.as_view(), name='cuenta-pagar-cancelar'),
    path('solicitar-cuenta', SolicitarCuentaView.as_view(), name='solicitar-cuenta'),
    path('mesa/comensales', MesaComensalesView.as_view(), name='mesa-comensales'),
    path('mesa/comensales/estado', MesaComensalesEstadoView.as_view(), name='mesa-comensales-estado'),
    path('mesa/comensales/ok', MesaOkView.as_view(), name='mesa-comensales-ok'),
    path('mesa/regenerar-pin', MesaRegenerarPinView.as_view(), name='mesa-regenerar-pin'),
    path('sesiones-mesa/<int:pk>/comensales', SesionComensalesView.as_view(), name='sesion-comensales'),
    path('sesiones-mesa/<int:pk>/liberar-ronda', SesionLiberarRondaView.as_view(), name='sesion-liberar-ronda'),
    path('sesiones-mesa/<int:pk>/regenerar-pin', SesionRegenerarPinView.as_view(), name='sesion-regenerar-pin'),
    path('sesiones-mesa/<int:pk>/pin/visto', SesionPinVistoView.as_view(), name='sesion-pin-visto'),
    path('pedidos/<uuid:uuid_comanda>/cancelar', ComandaCancelarView.as_view(), name='comanda-cancelar'),
    path('mesa/historial', HistorialMesaView.as_view(), name='historial-mesa'),
    path('pedidos', ComandaCreateView.as_view(), name='crear-comanda'),
    path('pedidos/<uuid:uuid_comanda>/estado', ComandaEstadoUpdateView.as_view(), name='actualizar-estado-comanda'),
    path('cocina/tablero', TableroCocinaView.as_view(), name='tablero-cocina'),
    path('pedidos/<uuid:uuid_comanda>/ticket', TicketPDFView.as_view(), name='ticket-comanda'),
    path('tickets/<uuid:uuid_comanda>.pdf', TicketPDFView.as_view(), name='ticket-comanda-pdf'),  # ruta que usa el front
]