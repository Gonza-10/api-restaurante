from django.db import models
from django.utils import timezone


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
    estado = models.BooleanField(default=False, db_column='Estado')  # True = ocupada
    activa = models.BooleanField(default=True, db_column='Activa')  # False = dada de baja (baja lógica)

    class Meta:
        db_table = 'Mesa'
        managed = False

    def __str__(self):
        return f'Mesa {self.numero}'


class Reserva(models.Model):
    """Reserva de una mesa para una jornada (fecha + turno). La carga Admin o Gerente. No tiene duracion: bloquea la mesa
    toda la jornada hasta que se cumple, se cancela o pasa la tolerancia de llegada (ver reservas.py)."""
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=80, db_column='Nombre')
    apellido = models.CharField(max_length=80, db_column='Apellido')
    telefono = models.CharField(max_length=20, db_column='Telefono')
    fecha = models.DateField(db_column='Fecha')
    hora = models.TimeField(db_column='Hora')  # hora de llegada acordada, dentro del horario del turno
    turno = models.ForeignKey('Turno', on_delete=models.PROTECT, db_column='IdTurno', related_name='reservas')
    cantidad_personas = models.IntegerField(default=1, db_column='CantidadPersonas')
    mesa = models.ForeignKey(Mesa, on_delete=models.SET_NULL, null=True, blank=True, db_column='IdMesa', related_name='reservas')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, db_column='IdEmpleado', related_name='reservas')
    estado = models.CharField(max_length=20, default='Confirmada', db_column='Estado')  # Confirmada / Cancelada / Cumplida / No se presentó
    notas = models.CharField(max_length=300, null=True, blank=True, db_column='Notas')
    origen = models.CharField(max_length=20, null=True, blank=True, db_column='Origen')  # Llamada / Mensaje / Otro
    fecha_hora_alta = models.DateTimeField(default=timezone.now, db_column='FechaHoraAlta')
    fecha_hora_cancelacion = models.DateTimeField(null=True, blank=True, db_column='FechaHoraCancelacion')
    empleado_cancelacion = models.ForeignKey(
        Empleado, on_delete=models.PROTECT, null=True, blank=True,
        db_column='IdEmpleadoCancelacion', related_name='reservas_canceladas'
    )
    motivo_cancelacion = models.CharField(max_length=200, null=True, blank=True, db_column='MotivoCancelacion')
    fecha_hora_resolucion = models.DateTimeField(null=True, blank=True, db_column='FechaHoraResolucion')
    pedido_cabecera = models.ForeignKey(
        'PedidoCabecera', on_delete=models.SET_NULL, null=True, blank=True,
        db_column='IdPedidoCabecera', related_name='reservas'
    )

    class Meta:
        db_table = 'Reserva'
        managed = False

    def __str__(self):
        return f'Reserva {self.id} - {self.nombre} {self.apellido}'


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
    descripcion = models.CharField(max_length=500, null=True, blank=True, db_column='Descripcion')
    imagen_url = models.CharField(max_length=500, null=True, blank=True, db_column='ImagenUrl')
    tiempo_estimado = models.PositiveIntegerField(null=True, blank=True, db_column='TiempoEstimadoMin')  # minutos
    porciones = models.PositiveIntegerField(null=True, blank=True, db_column='Porciones')  # personas que come
    # Disponibilidad: 'activo' es la decision de carta del Admin; estos dos los deciden el stock y Cocina
    disponible = models.BooleanField(default=True, db_column='Disponible')  # lo calcula el stock (0 = faltan insumos)
    agotado_manual = models.BooleanField(default=False, db_column='AgotadoManual')  # Cocina: "sin insumos"
    fecha_hora_agotado = models.DateTimeField(null=True, blank=True, db_column='FechaHoraAgotado')
    empleado_agotado = models.ForeignKey(
        'Empleado', null=True, blank=True, on_delete=models.SET_NULL, db_column='IdEmpleadoAgotado', related_name='+'
    )
    # receta que gasta una unidad de este producto; NULL = sin control de stock (por ejemplo una bebida cerrada)
    receta = models.ForeignKey(
        'Receta', null=True, blank=True, on_delete=models.PROTECT, db_column='IdReceta', related_name='productos'
    )

    class Meta:
        db_table = 'Producto'
        managed = False

    @property
    def visible_cliente(self):
        """El cliente solo ve el producto si esta en la carta, hay insumos y Cocina no lo agoto."""
        return self.activo and self.disponible and not self.agotado_manual

    def __str__(self):
        return self.nombre


class ProductoSugerido(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, db_column='IdProducto', related_name='sugerencias')
    producto_sugerido = models.ForeignKey(Producto, on_delete=models.CASCADE, db_column='IdProductoSugerido', related_name='sugerido_en')

    class Meta:
        db_table = 'ProductoSugerido'
        managed = False
        unique_together = (('producto', 'producto_sugerido'),)


# ==================== JORNADAS Y ESPECIALES ====================

class Turno(models.Model):
    """Horario de atencion del local (almuerzo, cena...). Si el cierre es menor o igual a la apertura,
    el turno termina al dia siguiente."""
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=30, db_column='Nombre')
    hora_apertura = models.TimeField(db_column='HoraApertura')
    hora_cierre = models.TimeField(db_column='HoraCierre')
    activo = models.BooleanField(default=True, db_column='Activo')

    class Meta:
        db_table = 'Turno'
        managed = False

    def __str__(self):
        return self.nombre


class Jornada(models.Model):
    """Periodo en que el local esta abierto al publico. Una sola abierta a la vez."""
    id = models.AutoField(primary_key=True, db_column='Id')
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, db_column='IdTurno', related_name='jornadas')
    fecha = models.DateField(db_column='Fecha')  # fecha local de apertura
    fecha_hora_apertura = models.DateTimeField(db_column='FechaHoraApertura')
    empleado_apertura = models.ForeignKey(
        Empleado, on_delete=models.PROTECT, db_column='IdEmpleadoApertura', related_name='jornadas_abiertas'
    )
    fecha_hora_cierre = models.DateTimeField(null=True, blank=True, db_column='FechaHoraCierre')
    empleado_cierre = models.ForeignKey(
        Empleado, on_delete=models.PROTECT, null=True, blank=True,
        db_column='IdEmpleadoCierre', related_name='jornadas_cerradas'
    )
    estado = models.CharField(max_length=10, default='Abierta', db_column='Estado')  # Abierta / Cerrada

    class Meta:
        db_table = 'Jornada'
        managed = False

    def __str__(self):
        return f'Jornada {self.fecha} ({self.turno.nombre})'


class DiaEspecial(models.Model):
    """Configuracion de una fecha puntual: sus especiales reemplazan a los semanales o se suman a ellos."""
    fecha = models.DateField(primary_key=True, db_column='Fecha')
    reemplaza = models.BooleanField(default=False, db_column='Reemplaza')
    nota = models.CharField(max_length=100, null=True, blank=True, db_column='Nota')

    class Meta:
        db_table = 'DiaEspecial'
        managed = False


class Especial(models.Model):
    """Plato con precio especial: regla semanal (dia_semana, 1=lunes ... 7=domingo) o fecha puntual.
    Sin turno vale todo el dia."""
    id = models.AutoField(primary_key=True, db_column='Id')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, db_column='IdProducto', related_name='especiales')
    precio_especial = models.DecimalField(max_digits=10, decimal_places=2, db_column='PrecioEspecial')
    turno = models.ForeignKey(
        Turno, on_delete=models.PROTECT, null=True, blank=True, db_column='IdTurno', related_name='especiales'
    )
    dia_semana = models.PositiveSmallIntegerField(null=True, blank=True, db_column='DiaSemana')
    fecha = models.DateField(null=True, blank=True, db_column='Fecha')

    class Meta:
        db_table = 'Especial'
        managed = False


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
    # cuando el cliente pidio la cuenta (NULL = todavia no la pidio)
    fecha_hora_solicita_cuenta = models.DateTimeField(null=True, blank=True, db_column='FechaHoraSolicitaCuenta')
    # con que medio dijo el cliente que quiere pagar al pedir la cuenta: Efectivo / MercadoPago / Tarjeta (NULL = no lo dijo)
    metodo_pago_solicitado = models.CharField(max_length=20, null=True, blank=True, db_column='MetodoPagoSolicitado')
    # cierre con saldo pendiente: solo Admin/Gerente y con motivo (hito 3)
    cierre_forzado = models.BooleanField(default=False, db_column='CierreForzado')
    motivo_cierre = models.CharField(max_length=200, null=True, blank=True, db_column='MotivoCierre')
    empleado_cierre = models.ForeignKey(
        Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleadoCierre', related_name='sesiones_cerradas'
    )
    # jornada en la que se abrio la mesa (NULL en las sesiones anteriores a las jornadas)
    jornada = models.ForeignKey(
        Jornada, on_delete=models.PROTECT, null=True, blank=True, db_column='IdJornada', related_name='sesiones'
    )
    # Familiar (todos agregan al pedido, la cuenta va a nombre de uno) o Grupal (nombre por dispositivo y OK de todos en la
    # primera ronda). RondaLiberada: la primera ronda ya salio a cocina (en una mesa Familiar nace liberada).
    modalidad = models.CharField(max_length=10, default='Familiar', db_column='Modalidad')
    ronda_liberada = models.BooleanField(default=False, db_column='RondaLiberada')
    # seguridad de la mesa: ultimo cambio de PIN (quien lo pidio), PIN viejos (para avisar "el PIN cambio") y aviso al mozo
    pin_regenerado_en = models.DateTimeField(null=True, blank=True, db_column='PinRegeneradoEn')
    pin_regenerado_por = models.CharField(max_length=80, null=True, blank=True, db_column='PinRegeneradoPor')
    pins_anteriores = models.CharField(max_length=60, null=True, blank=True, db_column='PinsAnteriores')
    aviso_pin_pendiente = models.BooleanField(default=False, db_column='AvisoPinPendiente')

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
    # a que comanda pertenece el item; NULL en los items anteriores a esta columna
    comanda = models.ForeignKey(
        'ComandaRecibida', on_delete=models.PROTECT, null=True, blank=True,
        db_column='IdComandaRecibida', related_name='detalles'
    )

    class Meta:
        db_table = 'PedidoDetalle'
        managed = False

    def __str__(self):
        return f'{self.cantidad}x {self.producto.nombre}'

class PedidoDetalleCompartido(models.Model):
    """Plato dividido: los participantes entre los que se reparte el renglon en partes iguales."""
    id = models.AutoField(primary_key=True, db_column='Id')
    detalle = models.ForeignKey(PedidoDetalle, on_delete=models.CASCADE, db_column='IdPedidoDetalle', related_name='compartido')
    participante = models.CharField(max_length=50, db_column='Participante')

    class Meta:
        db_table = 'PedidoDetalleCompartido'
        managed = False


class Comensal(models.Model):
    """Quien esta en la mesa. Nombre unico dentro de la sesion (sin distinguir mayusculas ni acentos)."""
    id = models.AutoField(primary_key=True, db_column='Id')
    pedido_cabecera = models.ForeignKey(PedidoCabecera, on_delete=models.CASCADE, db_column='IdPedidoCabecera', related_name='comensales')
    nombre = models.CharField(max_length=50, db_column='Nombre')
    fecha_hora_ingreso = models.DateTimeField(db_column='FechaHoraIngreso')
    estado = models.CharField(max_length=10, default='Activo', db_column='Estado')   # Activo / Retirado
    ok_primera_ronda = models.BooleanField(default=False, db_column='OkPrimeraRonda')
    fecha_hora_retiro = models.DateTimeField(null=True, blank=True, db_column='FechaHoraRetiro')

    class Meta:
        db_table = 'Comensal'
        managed = False

    def __str__(self):
        return self.nombre


class ComandaRecibida(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    id_comanda_uuid = models.UUIDField(unique=True, db_column='IdComandaUuid')
    pedido_cabecera = models.ForeignKey(
        PedidoCabecera, on_delete=models.PROTECT,
        db_column='IdPedidoCabecera', related_name='comandas'
    )
    fecha_hora_recepcion = models.DateTimeField(db_column='FechaHoraRecepcion')
    # Aceptada; Rechazada si al llegar no alcanzaba el stock (sin items, no descuenta nada); Cancelada si se cancelo antes de
    # prepararse (stock devuelto, sin renglones en la cuenta; el motivo queda en `motivo`)
    estado = models.CharField(max_length=10, default='Aceptada', db_column='Estado')
    comensal = models.ForeignKey(
        'Comensal', on_delete=models.PROTECT, null=True, blank=True, db_column='IdComensal', related_name='comandas'
    )
    fecha_hora_cancelacion = models.DateTimeField(null=True, blank=True, db_column='FechaHoraCancelacion')
    motivo = models.CharField(max_length=500, null=True, blank=True, db_column='Motivo')  # interno: solo personal
    mensaje_cliente = models.CharField(max_length=300, null=True, blank=True, db_column='MensajeCliente')

    class Meta:
        db_table = 'ComandaRecibida'
        managed = False

    def __str__(self):
        return str(self.id_comanda_uuid)

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
    """La cuenta interna (sin ARCA) de una sesion de mesa. Una vigente por sesion. Se emite al empezar a cobrar y congela
    el total y los renglones. Estado: Emitida | Pagada | Anulada. `total` esta en pesos; total_usd/brl/pyg son la foto de
    cuanto equivale con las cotizaciones de ese momento (NULL solo si todavia no habia ninguna cotizacion guardada)."""
    id = models.AutoField(primary_key=True, db_column='Id')
    pedido_cabecera = models.ForeignKey(PedidoCabecera, on_delete=models.PROTECT, db_column='IdPedidoCabecera', related_name='facturas')
    fecha_hora_emision = models.DateTimeField(db_column='FechaHoraEmision')
    total = models.DecimalField(max_digits=14, decimal_places=2, db_column='Total')
    # Casilla "quiero factura" (hito 6): el cliente pidio el comprobante PDF. La factura interna existe igual; lo opcional es el PDF.
    solicito_ticket = models.BooleanField(default=False, db_column='SolicitoTicket')
    nombre_factura = models.CharField(max_length=100, null=True, blank=True, db_column='NombreFactura')  # script 22: nombre en el PDF y en su archivo
    cambio_entregado = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='CambioEntregado')
    total_usd = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='TotalUSD')
    total_brl = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='TotalBRL')
    total_pyg = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='TotalPYG')
    cotizacion_usd = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True, db_column='CotizacionUSD')
    cotizacion_brl = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True, db_column='CotizacionBRL')
    cotizacion_pyg = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True, db_column='CotizacionPYG')
    estado = models.CharField(max_length=10, default='Emitida', db_column='Estado')
    fecha_hora_pago = models.DateTimeField(null=True, blank=True, db_column='FechaHoraPago')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleado', related_name='facturas_emitidas')
    fecha_hora_anulacion = models.DateTimeField(null=True, blank=True, db_column='FechaHoraAnulacion')
    empleado_anulacion = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleadoAnulacion', related_name='facturas_anuladas')
    motivo_anulacion = models.CharField(max_length=200, null=True, blank=True, db_column='MotivoAnulacion')

    class Meta:
        db_table = 'Factura'
        managed = False


class FacturaDetalle(models.Model):
    """Un renglon de la factura: copia de lo consumido, con el nombre y el precio de ese momento."""
    id = models.AutoField(primary_key=True, db_column='Id')
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, db_column='IdFactura', related_name='detalles')
    pedido_detalle = models.ForeignKey(PedidoDetalle, on_delete=models.SET_NULL, null=True, blank=True, db_column='IdPedidoDetalle', related_name='+')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, db_column='IdProducto', related_name='+')
    descripcion = models.CharField(max_length=150, db_column='Descripcion')
    cantidad = models.IntegerField(db_column='Cantidad')
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, db_column='PrecioUnitario')
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, db_column='SubTotal')
    identificador_comensal = models.CharField(max_length=50, null=True, blank=True, db_column='IdentificadorComensal')

    class Meta:
        db_table = 'FacturaDetalle'
        managed = False


class Pago(models.Model):
    """Una parte del cobro de una factura. `monto` es lo que descuenta de la cuenta (pesos). Estado: Pendiente | Aprobado |
    Rechazado | Cancelado | Expirado | Anulado. El efectivo nace Aprobado y es el unico que se anula."""
    id = models.AutoField(primary_key=True, db_column='Id')
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, db_column='IdFactura', related_name='pagos')
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.PROTECT, db_column='IdMetodoPago', related_name='pagos')
    monto = models.DecimalField(max_digits=14, decimal_places=2, db_column='Monto')
    referencia_externa = models.CharField(max_length=100, null=True, blank=True, db_column='ReferenciaExterna')
    fecha_hora = models.DateTimeField(db_column='FechaHora')
    estado = models.CharField(max_length=10, default='Aprobado', db_column='Estado')
    moneda = models.CharField(max_length=3, default='ARS', db_column='Moneda')
    monto_recibido = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='MontoRecibido')  # en `moneda`
    cotizacion = models.DecimalField(max_digits=18, decimal_places=8, default=1, db_column='Cotizacion')  # ARS por 1 unidad; congelada
    monto_propina = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_column='MontoPropina')  # pesos
    vuelto = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_column='Vuelto')  # siempre en pesos
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleado', related_name='pagos_registrados')
    empleado_propina = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleadoPropina', related_name='propinas')
    clave_idempotencia = models.CharField(max_length=36, null=True, blank=True, db_column='ClaveIdempotencia')
    fecha_hora_anulacion = models.DateTimeField(null=True, blank=True, db_column='FechaHoraAnulacion')
    empleado_anulacion = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleadoAnulacion', related_name='pagos_anulados')
    motivo_anulacion = models.CharField(max_length=200, null=True, blank=True, db_column='MotivoAnulacion')
    # Mercado Pago (script 20). `referencia_externa` guarda nuestra referencia 'SG-<id>' (external_reference en MP).
    mp_preferencia_id = models.CharField(max_length=100, null=True, blank=True, db_column='MpPreferenciaId')
    mp_url_pago = models.CharField(max_length=500, null=True, blank=True, db_column='MpUrlPago')
    fecha_hora_expiracion = models.DateTimeField(null=True, blank=True, db_column='FechaHoraExpiracion')
    mp_pago_id = models.CharField(max_length=40, null=True, blank=True, db_column='MpPagoId')
    mp_estado = models.CharField(max_length=30, null=True, blank=True, db_column='MpEstado')
    mp_monto_neto = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='MpMontoNeto')

    class Meta:
        db_table = 'Pago'
        managed = False


class PagoEvento(models.Model):
    """Historial de un pago (auditoria): que paso, cuando y quien."""
    id = models.AutoField(primary_key=True, db_column='Id')
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, db_column='IdPago', related_name='eventos')
    fecha_hora = models.DateTimeField(db_column='FechaHora')
    evento = models.CharField(max_length=30, db_column='Evento')
    estado_anterior = models.CharField(max_length=10, null=True, blank=True, db_column='EstadoAnterior')
    estado_nuevo = models.CharField(max_length=10, db_column='EstadoNuevo')
    detalle = models.CharField(max_length=400, null=True, blank=True, db_column='Detalle')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleado', related_name='+')

    class Meta:
        db_table = 'PagoEvento'
        managed = False


class CotizacionMoneda(models.Model):
    """Cotizacion oficial de una moneda (USD, BRL, PYG): ARS por 1 unidad. Se guarda una fila nueva solo cuando el valor
    cambia (worker_cotizacion.py, desde el BCRA); la vigente es la ultima de cada moneda. Nadie la carga a mano."""
    id = models.AutoField(primary_key=True, db_column='Id')
    moneda = models.CharField(max_length=3, db_column='Moneda')
    valor = models.DecimalField(max_digits=18, decimal_places=8, db_column='Valor')
    fecha = models.DateField(db_column='Fecha')  # fecha de la cotizacion segun la fuente (dia habil al que corresponde)
    fuente = models.CharField(max_length=30, default='BCRA', db_column='Fuente')
    fecha_hora = models.DateTimeField(db_column='FechaHora')  # cuando la guardamos

    class Meta:
        db_table = 'CotizacionMoneda'
        managed = False


class Caja(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    empleado_apertura = models.ForeignKey(Empleado, on_delete=models.PROTECT, db_column='IdEmpleadoApertura', related_name='cajas_abiertas')
    fecha_hora_apertura = models.DateTimeField(db_column='FechaHoraApertura')
    monto_apertura = models.DecimalField(max_digits=14, decimal_places=2, db_column='MontoApertura')  # efectivo en pesos; el detalle por moneda esta en CajaMoneda
    empleado_cierre = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleadoCierre', related_name='cajas_cerradas')
    fecha_hora_cierre = models.DateTimeField(null=True, blank=True, db_column='FechaHoraCierre')
    monto_cierre = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='MontoCierre')  # efectivo en pesos contado al cerrar
    estado = models.CharField(max_length=20, default='Abierta', db_column='Estado')
    total_esperado_ars = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='TotalEsperadoARS')    # efectivo en pesos + Mercado Pago, al cerrar
    total_declarado_ars = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='TotalDeclaradoARS')

    class Meta:
        db_table = 'Caja'
        managed = False


class CajaMoneda(models.Model):
    """Una fila por caja, medio y moneda. Efectivo: ARS, USD, BRL y PYG (lo que habia al abrir y, al cerrar, lo esperado, lo
    contado y la diferencia). MercadoPago: una sola fila en ARS con lo esperado, lo acreditado y la diferencia al cerrar."""
    id = models.AutoField(primary_key=True, db_column='Id')
    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, db_column='IdCaja', related_name='monedas')
    medio = models.CharField(max_length=20, default='Efectivo', db_column='Medio')  # Efectivo | MercadoPago
    moneda = models.CharField(max_length=3, db_column='Moneda')
    monto_apertura = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_column='MontoApertura')
    monto_esperado = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='MontoEsperado')
    monto_declarado = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='MontoDeclarado')
    diferencia = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_column='Diferencia')  # declarado - esperado

    class Meta:
        db_table = 'CajaMoneda'
        managed = False


class MovimientoCaja(models.Model):
    """Entrada o salida de dinero de la caja. `medio` dice donde esta ese dinero: Efectivo (el cajon) o MercadoPago (la cuenta
    digital: se anota cuando el pago se aprueba). `monto` esta en `moneda`; `cotizacion` es ARS por 1 unidad vigente en ese
    momento (1 si es ARS) y `monto_ars` el equivalente en pesos. Tipo: Ingreso | Egreso. Concepto: Manual | Venta |
    Propina | Vuelto | Anulacion."""
    id = models.AutoField(primary_key=True, db_column='Id')
    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, db_column='IdCaja', related_name='movimientos')
    tipo = models.CharField(max_length=20, db_column='Tipo')
    concepto = models.CharField(max_length=20, default='Manual', db_column='Concepto')
    medio = models.CharField(max_length=20, default='Efectivo', db_column='Medio')  # Efectivo (cajon) | MercadoPago (cuenta digital, solo ARS)
    moneda = models.CharField(max_length=3, default='ARS', db_column='Moneda')
    monto = models.DecimalField(max_digits=14, decimal_places=2, db_column='Monto')
    cotizacion = models.DecimalField(max_digits=18, decimal_places=8, default=1, db_column='Cotizacion')
    monto_ars = models.DecimalField(max_digits=14, decimal_places=2, db_column='MontoARS')
    descripcion = models.CharField(max_length=200, null=True, blank=True, db_column='Descripcion')
    fecha_hora = models.DateTimeField(db_column='FechaHora')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleado', related_name='movimientos_caja')  # NULL: lo registro el sistema (Mercado Pago)
    pago = models.ForeignKey(Pago, on_delete=models.SET_NULL, null=True, blank=True, db_column='IdPago', related_name='movimientos_caja')

    class Meta:
        db_table = 'MovimientoCaja'
        managed = False

# ==================== STOCK (hito 1) ====================
# Las cantidades estan siempre en UNIDAD BASE: gramos, mililitros o unidades segun el TipoMedida del insumo.

class Proveedor(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    contacto = models.CharField(max_length=100, null=True, blank=True, db_column='Contacto')
    telefono = models.CharField(max_length=30, null=True, blank=True, db_column='Telefono')
    email = models.CharField(max_length=120, null=True, blank=True, db_column='Email')
    direccion = models.CharField(max_length=200, null=True, blank=True, db_column='Direccion')
    notas = models.CharField(max_length=300, null=True, blank=True, db_column='Notas')
    activo = models.BooleanField(default=True, db_column='Activo')  # baja logica: conserva el historial de compras

    class Meta:
        db_table = 'Proveedor'
        managed = False

    def __str__(self):
        return self.nombre


class Insumo(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    tipo_medida = models.CharField(max_length=10, db_column='TipoMedida')  # Masa / Volumen / Unidad
    stock_objetivo = models.DecimalField(max_digits=12, decimal_places=3, default=0, db_column='StockObjetivo')  # el 100%
    umbral_bajo_pct = models.PositiveSmallIntegerField(default=50, db_column='UmbralBajoPct')  # amarillo
    umbral_critico_pct = models.PositiveSmallIntegerField(default=20, db_column='UmbralCriticoPct')  # rojo
    # Dias de aviso de vencimiento propios de este insumo (hito 6.1). NULL = usa los generales de la configuracion.
    dias_aviso_vencimiento = models.PositiveSmallIntegerField(null=True, blank=True, db_column='DiasAvisoVencimiento')
    activo = models.BooleanField(default=True, db_column='Activo')

    class Meta:
        db_table = 'Insumo'
        managed = False

    def __str__(self):
        return self.nombre


# La tabla InsumoProveedor (insumo <-> proveedor, sin columna Id) se maneja con SQL directo en stock.py.


class Compra(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, db_column='IdProveedor', related_name='compras')
    fecha_hora = models.DateTimeField(db_column='FechaHora')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, db_column='IdEmpleado', related_name='+')
    jornada = models.ForeignKey(Jornada, on_delete=models.PROTECT, null=True, blank=True, db_column='IdJornada', related_name='+')
    numero_comprobante = models.CharField(max_length=50, null=True, blank=True, db_column='NumeroComprobante')
    nota = models.CharField(max_length=300, null=True, blank=True, db_column='Nota')

    class Meta:
        db_table = 'Compra'
        managed = False


class LoteInsumo(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, db_column='IdInsumo', related_name='lotes')
    compra = models.ForeignKey(Compra, on_delete=models.PROTECT, null=True, blank=True, db_column='IdCompra', related_name='lotes')
    origen = models.CharField(max_length=12, default='Compra', db_column='Origen')  # Compra / Ajuste / Elaboracion
    fecha_ingreso = models.DateTimeField(db_column='FechaIngreso')
    fecha_vencimiento = models.DateField(null=True, blank=True, db_column='FechaVencimiento')
    tamano_presentacion = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, db_column='TamanoPresentacion')
    cantidad_presentaciones = models.IntegerField(null=True, blank=True, db_column='CantidadPresentaciones')
    cantidad_inicial = models.DecimalField(max_digits=12, decimal_places=3, db_column='CantidadInicial')
    cantidad_actual = models.DecimalField(max_digits=12, decimal_places=3, db_column='CantidadActual')
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=6, db_column='CostoUnitario')  # por unidad base
    estado = models.CharField(max_length=10, default='Activo', db_column='Estado')  # Activo / Agotado / Vencido / Baja

    class Meta:
        db_table = 'LoteInsumo'
        managed = False


class Perdida(models.Model):
    """Perdida registrada por el personal (hito 4): un insumo suelto o un plato ya cocinado, con motivo de lista cerrada.
    El valor no se guarda: sale de los movimientos del libro (cada uno con el costo real de su lote)."""
    id = models.AutoField(primary_key=True, db_column='Id')
    fecha_hora = models.DateTimeField(db_column='FechaHora')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, db_column='IdEmpleado', related_name='+')
    jornada = models.ForeignKey(Jornada, on_delete=models.PROTECT, null=True, blank=True, db_column='IdJornada', related_name='+')
    alcance = models.CharField(max_length=10, db_column='Alcance')  # Insumo / Plato
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, null=True, blank=True, db_column='IdInsumo', related_name='perdidas')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, null=True, blank=True, db_column='IdProducto', related_name='perdidas')
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, db_column='Cantidad')  # insumo: unidad base; plato: platos enteros
    motivo = models.CharField(max_length=20, db_column='Motivo')  # codigo de la lista cerrada (ver stock_calculos.MOTIVOS_PERDIDA)
    nota = models.CharField(max_length=300, null=True, blank=True, db_column='Nota')

    class Meta:
        db_table = 'Perdida'
        managed = False


class MovimientoStock(models.Model):
    """Libro de movimientos: nunca se edita ni se borra. Cantidad con signo (+ entra, - sale)."""
    id = models.BigAutoField(primary_key=True, db_column='Id')
    lote = models.ForeignKey(LoteInsumo, on_delete=models.PROTECT, db_column='IdLote', related_name='movimientos')
    tipo = models.CharField(max_length=12, db_column='Tipo')
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, db_column='Cantidad')
    fecha_hora = models.DateTimeField(db_column='FechaHora')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleado', related_name='+')
    jornada = models.ForeignKey(Jornada, on_delete=models.PROTECT, null=True, blank=True, db_column='IdJornada', related_name='+')
    comanda = models.ForeignKey(
        ComandaRecibida, on_delete=models.PROTECT, null=True, blank=True, db_column='IdComandaRecibida', related_name='+'
    )
    perdida = models.ForeignKey(
        Perdida, on_delete=models.PROTECT, null=True, blank=True, db_column='IdPerdida', related_name='movimientos'
    )
    produccion = models.ForeignKey(
        'Produccion', on_delete=models.PROTECT, null=True, blank=True, db_column='IdProduccion', related_name='movimientos'
    )
    motivo = models.CharField(max_length=100, null=True, blank=True, db_column='Motivo')
    nota = models.CharField(max_length=300, null=True, blank=True, db_column='Nota')

    class Meta:
        db_table = 'MovimientoStock'
        managed = False


class StockInsumo(models.Model):
    """Vista vw_StockInsumo (solo lectura): stock actual de cada insumo, porcentaje del objetivo y semaforo."""
    insumo = models.OneToOneField(
        Insumo, primary_key=True, on_delete=models.DO_NOTHING, db_column='IdInsumo', related_name='stock'
    )
    nombre = models.CharField(max_length=100, db_column='Nombre')
    tipo_medida = models.CharField(max_length=10, db_column='TipoMedida')
    stock_objetivo = models.DecimalField(max_digits=12, decimal_places=3, db_column='StockObjetivo')
    umbral_bajo_pct = models.PositiveSmallIntegerField(db_column='UmbralBajoPct')
    umbral_critico_pct = models.PositiveSmallIntegerField(db_column='UmbralCriticoPct')
    activo = models.BooleanField(db_column='Activo')
    stock_actual = models.DecimalField(max_digits=14, decimal_places=3, db_column='StockActual')
    porcentaje = models.DecimalField(max_digits=7, decimal_places=1, null=True, db_column='Porcentaje')
    estado = models.CharField(max_length=12, db_column='Estado')  # Agotado / SinObjetivo / Critico / Bajo / Ok

    class Meta:
        db_table = 'vw_StockInsumo'
        managed = False


# ==================== RECETAS (hito 2) ====================

class Receta(models.Model):
    """Que insumos gasta UNA unidad vendida. Los productos del menu la referencian (Producto.receta)."""
    id = models.AutoField(primary_key=True, db_column='Id')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    descripcion = models.CharField(max_length=300, null=True, blank=True, db_column='Descripcion')
    # Elaboracion (hito 6): si esta receta cocina un insumo propio (salsa, masa), cual y cuanto sale de UNA tanda.
    # Sin insumo_producido es una receta de plato, como siempre.
    insumo_producido = models.OneToOneField(
        'Insumo', on_delete=models.PROTECT, null=True, blank=True, db_column='IdInsumoProducido', related_name='elaboracion'
    )
    rinde = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, db_column='Rinde')  # unidad base del insumo producido
    dias_vencimiento = models.IntegerField(null=True, blank=True, db_column='DiasVencimiento')  # vida util del lote producido

    class Meta:
        db_table = 'Receta'
        managed = False

    def __str__(self):
        return self.nombre


class RecetaIngrediente(models.Model):
    id = models.AutoField(primary_key=True, db_column='Id')
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, db_column='IdReceta', related_name='ingredientes')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, db_column='IdInsumo', related_name='usos_en_recetas')
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, db_column='Cantidad')  # unidad base, por unidad vendida
    es_quitable = models.BooleanField(default=False, db_column='EsQuitable')  # el cliente puede pedir el plato SIN este ingrediente (hito 5)

    class Meta:
        db_table = 'RecetaIngrediente'
        managed = False


class PedidoDetalleModificador(models.Model):
    """Lo que se quito en un renglon del pedido (hito 5): un registro por ingrediente quitado ("sin cebolla").
    Lo quitado no se descuenta del stock."""
    id = models.AutoField(primary_key=True, db_column='Id')
    detalle = models.ForeignKey(
        PedidoDetalle, on_delete=models.CASCADE, db_column='IdPedidoDetalle', related_name='modificadores'
    )
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, db_column='IdInsumo', related_name='+')

    class Meta:
        db_table = 'PedidoDetalleModificador'
        managed = False


class RecetaExtra(models.Model):
    """Un extra que se puede sumar a los platos de una receta (cobros, hito 5): mas cheddar, aderezo. Gasta `cantidad` del
    insumo por cada unidad de extra y cobra `precio` por unidad. No se borra (queda en el historial): se desactiva."""
    id = models.AutoField(primary_key=True, db_column='Id')
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, db_column='IdReceta', related_name='extras')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, db_column='IdInsumo', related_name='usos_como_extra')
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, db_column='Cantidad')   # unidad base, por unidad de extra
    precio = models.DecimalField(max_digits=10, decimal_places=2, db_column='Precio')       # recargo por unidad de extra
    max_por_unidad = models.IntegerField(default=1, db_column='MaxPorUnidad')               # unidades de extra por unidad de plato
    activo = models.BooleanField(default=True, db_column='Activo')
    disponible = models.BooleanField(default=True, db_column='Disponible')                  # lo calcula el stock

    class Meta:
        db_table = 'RecetaExtra'
        managed = False


class PedidoDetalleExtra(models.Model):
    """Los extras de un renglon del pedido, con el recargo congelado al pedir. El precio del renglon ya los incluye."""
    id = models.AutoField(primary_key=True, db_column='Id')
    detalle = models.ForeignKey(PedidoDetalle, on_delete=models.CASCADE, db_column='IdPedidoDetalle', related_name='extras')
    extra = models.ForeignKey(RecetaExtra, on_delete=models.PROTECT, db_column='IdRecetaExtra', related_name='+')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, db_column='IdInsumo', related_name='+')
    cantidad = models.IntegerField(db_column='Cantidad')                                    # unidades de extra por unidad de plato
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, db_column='PrecioUnitario')

    class Meta:
        db_table = 'PedidoDetalleExtra'
        managed = False


# ==================== ELABORACIONES, VENCIMIENTOS Y CONFIGURACION (hito 6) ====================

class Produccion(models.Model):
    """Una elaboracion registrada por Cocina: cuantas tandas de una receta de elaboracion se cocinaron. Los consumos de
    los ingredientes y el ingreso del lote producido estan en el libro, enlazados por MovimientoStock.produccion."""
    id = models.AutoField(primary_key=True, db_column='Id')
    fecha_hora = models.DateTimeField(db_column='FechaHora')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, db_column='IdEmpleado', related_name='+')
    jornada = models.ForeignKey(Jornada, on_delete=models.PROTECT, null=True, blank=True, db_column='IdJornada', related_name='+')
    receta = models.ForeignKey(Receta, on_delete=models.PROTECT, db_column='IdReceta', related_name='producciones')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, db_column='IdInsumo', related_name='producciones')
    tandas = models.DecimalField(max_digits=12, decimal_places=3, db_column='Tandas')
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, db_column='Cantidad')  # lo que salio (rinde x tandas)
    nota = models.CharField(max_length=300, null=True, blank=True, db_column='Nota')

    class Meta:
        db_table = 'Produccion'
        managed = False


class Configuracion(models.Model):
    """Parametros del stock que Admin y Gerente pueden cambiar (clave/valor)."""
    clave = models.CharField(max_length=50, primary_key=True, db_column='Clave')
    valor = models.CharField(max_length=200, db_column='Valor')
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=True, blank=True, db_column='IdEmpleado', related_name='+')
    actualizado_en = models.DateTimeField(db_column='ActualizadoEn')

    class Meta:
        db_table = 'Configuracion'
        managed = False
