from django.contrib import admin

from .models import (
    Rol,
    Empleado,
    Mesa,
    Categoria,
    Producto,
    ProductoSugerido,
    PedidoCabecera,
    PedidoDetalle,
    Reserva,
    MetodoPago,
    Factura,
    Pago,
    CotizacionMoneda,
    Caja,
    MovimientoCaja,
)

admin.site.register(Rol)
admin.site.register(Empleado)
admin.site.register(Mesa)
admin.site.register(Categoria)
admin.site.register(Producto)
admin.site.register(ProductoSugerido)
admin.site.register(PedidoCabecera)
admin.site.register(PedidoDetalle)
admin.site.register(Reserva)
admin.site.register(MetodoPago)
admin.site.register(Factura)
admin.site.register(Pago)
admin.site.register(CotizacionMoneda)
admin.site.register(Caja)
admin.site.register(MovimientoCaja)