from django.db import models


# ==================== IDENTIDAD Y ACCESO ====================

class Rol(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=30, db_column='Nombre')

    class Meta:
        db_table = 'Rol'
        managed = False

    def __str__(self):
        return self.nombre


class Empleado(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=80, db_column='Nombre')
    apellido = models.CharField(max_length=80, db_column='Apellido')
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, db_column='IdRol', related_name='empleados')
    usuario = models.CharField(max_length=50, db_column='Usuario')
    contrasena_hash = models.CharField(max_length=256, db_column='ContraseñaHash')
    activo = models.BooleanField(default=True, db_column='Activo')
    fecha_ingreso = models.DateTimeField(db_column='FechaIngreso')

    class Meta:
        db_table = 'Empleado'
        managed = False

    def __str__(self):
        return f'{self.nombre} {self.apellido}'


# ==================== MESAS Y RESERVAS ====================

class Mesa(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    numero = models.IntegerField(db_column='Numero')
    capacidad_maxima = models.IntegerField(db_column='CapacidadMaxima')
    estado = models.BooleanField(default=False, db_column='Estado')

    class Meta:
        db_table = 'Mesa'
        managed = False

    def __str__(self):
        return f'Mesa {self.numero}'


class Reserva(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=80, db_column='Nombre')
    apellido = models.CharField(max_length=80, db_column='Apellido')
    telefono = models.CharField(max_length=20, db_column='Telefono')
    fecha = models.DateField(db_column='Fecha')
    hora = models.TimeField(db_column='Hora')
    mesa = models.ForeignKey(Mesa, on_delete=models.SET_NULL, null=True, blank=True, db_column='IdMesa', related_name='reservas')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, db_column='IdEmpleado', related_name='reservas')
    estado = models.CharField(max_length=20, default='Confirmada', db_column='Estado')

    class Meta:
        db_table = 'Reserva'
        managed = False


# ==================== MENÚ ====================

class Categoria(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=50, db_column='Nombre')

    class Meta:
        db_table = 'Categoria'
        managed = False

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=80, db_column='Nombre')
    precio_actual = models.DecimalField(max_digits=10, decimal_places=2, db_column='PrecioActual')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, db_column='IdCategoria', related_name='productos')
    es_vegetariano = models.BooleanField(default=False, db_column='EsVegetariano')
    apto_celiaco = models.BooleanField(default=False, db_column='AptoCeliaco')
    activo = models.BooleanField(default=True, db_column='Activo')

    class Meta:
        db_table = 'Producto'
        managed = False

    def __str__(self):
        return self.nombre


class ProductoSugerido(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, db_column='IdProducto', related_name='sugerencias')
    producto_sugerido = models.ForeignKey(Producto, on_delete=models.CASCADE, db_column='IdProductoSugerido', related_name='sugerido_en')

    class Meta:
        db_table = 'ProductoSugerido'
        managed = False
        unique_together = (('producto', 'producto_sugerido'),)


# ==================== PEDIDOS ====================

class PedidoCabecera(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    mesa = models.ForeignKey(Mesa, on_delete=models.PROTECT, db_column='IdMesa', related_name='pedidos')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, db_column='IdEmpleado', related_name='pedidos_abiertos')
    codigo_pin = models.CharField(max_length=4, db_column='CodigoPin')
    fecha_hora_apertura = models.DateTimeField(db_column='FechaHoraApertura')
    fecha_hora_cierre = models.DateTimeField(null=True, blank=True, db_column='FechaHoraCierre')
    cantidad_comensales = models.IntegerField(db_column='CantidadComensales')
    estado = models.CharField(max_length=20, default='Abierto', db_column='Estado')

    class Meta:
        db_table = 'PedidoCabecera'
        managed = False

    def __str__(self):
        return f'Pedido #{self.id} - Mesa {self.mesa.numero}'


class PedidoDetalle(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    pedido_cabecera = models.ForeignKey(PedidoCabecera, on_delete=models.CASCADE, db_column='IdPedidoCabecera', related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, db_column='IdProducto', related_name='detalles_pedido')
    cantidad = models.IntegerField(db_column='Cantidad')
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, db_column='PrecioUnitario')
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, db_column='SubTotal')
    identificador_comensal = models.CharField(max_length=50, null=True, blank=True, db_column='IdentificadorComensal')
    estado_cocina = models.BooleanField(default=False, db_column='EstadoCocina')

    class Meta:
        db_table = 'PedidoDetalle'
        managed = False

    def __str__(self):
        return f'{self.cantidad}x {self.producto.nombre}'


# ==================== PAGOS Y CAJA (secundarias, encaminadas) ====================

class MetodoPago(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=30, db_column='Nombre')

    class Meta:
        db_table = 'MetodoPago'
        managed = False

    def __str__(self):
        return self.nombre


class Factura(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    pedido_cabecera = models.ForeignKey(PedidoCabecera, on_delete=models.PROTECT, db_column='IdPedidoCabecera', related_name='facturas')
    fecha_hora_emision = models.DateTimeField(db_column='FechaHoraEmision')
    total = models.DecimalField(max_digits=10, decimal_places=2, db_column='Total')
    solicito_ticket = models.BooleanField(default=False, db_column='SolicitoTicket')
    cambio_entregado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, db_column='CambioEntregado')
    total_usd = models.DecimalField(max_digits=10, decimal_places=2, db_column='TotalUSD')
    total_brl = models.DecimalField(max_digits=10, decimal_places=2, db_column='TotalBRL')
    total_pyg = models.DecimalField(max_digits=10, decimal_places=2, db_column='TotalPYG')

    class Meta:
        db_table = 'Factura'
        managed = False


class Pago(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, db_column='IdFactura', related_name='pagos')
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.PROTECT, db_column='IdMetodoPago', related_name='pagos')
    monto = models.DecimalField(max_digits=10, decimal_places=2, db_column='Monto')
    referencia_externa = models.CharField(max_length=100, null=True, blank=True, db_column='ReferenciaExterna')
    fecha_hora = models.DateTimeField(db_column='FechaHora')

    class Meta:
        db_table = 'Pago'
        managed = False


class CotizacionMoneda(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    moneda = models.CharField(max_length=3, db_column='Moneda')
    valor = models.DecimalField(max_digits=10, decimal_places=4, db_column='Valor')
    fecha = models.DateField(db_column='Fecha')

    class Meta:
        db_table = 'CotizacionMoneda'
        managed = False


class Caja(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    empleado_apertura = models.ForeignKey(Empleado, on_delete=models.PROTECT, db_column='IdEmpleadoApertura', related_name='cajas_abiertas')
    fecha_hora_apertura = models.DateTimeField(db_column='FechaHoraApertura')
    monto_apertura = models.DecimalField(max_digits=10, decimal_places=2, db_column='MontoApertura')
    empleado_cierre = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleadoCierre', related_name='cajas_cerradas')
    fecha_hora_cierre = models.DateTimeField(null=True, blank=True, db_column='FechaHoraCierre')
    monto_cierre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, db_column='MontoCierre')
    estado = models.CharField(max_length=20, default='Abierta', db_column='Estado')

    class Meta:
        db_table = 'Caja'
        managed = False


class MovimientoCaja(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, db_column='IdCaja', related_name='movimientos')
    tipo = models.CharField(max_length=20, db_column='Tipo')
    monto = models.DecimalField(max_digits=10, decimal_places=2, db_column='Monto')
    descripcion = models.CharField(max_length=200, null=True, blank=True, db_column='Descripcion')
    fecha_hora = models.DateTimeField(db_column='FechaHora')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, db_column='IdEmpleado', related_name='movimientos_caja')
    pago = models.ForeignKey(Pago, on_delete=models.SET_NULL, null=True, blank=True, db_column='IdPago', related_name='movimientos_caja')

    class Meta:
        db_table = 'MovimientoCaja'
        managed = False