-- =====================================================================================
-- Diagnostico del entorno (SOLO LECTURA: no modifica nada).
-- Ejecutar en SSMS conectado a la base RestauranteDB (o a la que se este usando).
-- Dice que scripts faltan correr y si hay datos base (turnos, mesas, roles, empleados, productos).
-- Columna Estado: OK / FALTA. Si algo dice FALTA, correr el script indicado en Detalle (ver README).
-- =====================================================================================
SET NOCOUNT ON;

DECLARE @r TABLE (Orden INT IDENTITY(1,1), Chequeo NVARCHAR(60), Estado NVARCHAR(6), Detalle NVARCHAR(200));

-- ---------- tablas ----------
INSERT @r (Chequeo, Estado, Detalle)
SELECT t.Nombre, IIF(OBJECT_ID('dbo.' + t.Nombre, 'U') IS NULL, 'FALTA', 'OK'), t.Script
FROM (VALUES
    (N'Rol',              N'00_Creacion_RestauranteDB.sql'),
    (N'Empleado',         N'00_Creacion_RestauranteDB.sql'),
    (N'Mesa',             N'00_Creacion_RestauranteDB.sql'),
    (N'Producto',         N'00_Creacion_RestauranteDB.sql'),
    (N'PedidoCabecera',   N'00_Creacion_RestauranteDB.sql'),
    (N'ComandaRecibida',  N'01_AE2_Migraciones.sql'),
    (N'Turno',            N'08_AE4_Jornada_Migraciones.sql'),
    (N'Jornada',          N'08_AE4_Jornada_Migraciones.sql'),
    (N'Especial',         N'09_AE4_Especiales_Migraciones.sql'),
    (N'DiaEspecial',      N'09_AE4_Especiales_Migraciones.sql'),
    (N'Proveedor',        N'11_AE4_Stock_Insumos_Migraciones.sql'),
    (N'Insumo',           N'11_AE4_Stock_Insumos_Migraciones.sql'),
    (N'InsumoProveedor',  N'11_AE4_Stock_Insumos_Migraciones.sql'),
    (N'Compra',           N'11_AE4_Stock_Insumos_Migraciones.sql'),
    (N'LoteInsumo',       N'11_AE4_Stock_Insumos_Migraciones.sql'),
    (N'MovimientoStock',  N'11_AE4_Stock_Insumos_Migraciones.sql'),
    (N'Receta',           N'12_AE4_Recetas_Migraciones.sql'),
    (N'RecetaIngrediente',N'12_AE4_Recetas_Migraciones.sql'),
    (N'Perdida',          N'13_AE4_Perdidas_Migraciones.sql'),
    (N'PedidoDetalleModificador', N'14_AE4_Modificadores_Migraciones.sql'),
    (N'Produccion',       N'15_AE4_Elaboraciones_Vencimientos_Migraciones.sql'),
    (N'Configuracion',    N'15_AE4_Elaboraciones_Vencimientos_Migraciones.sql'),
    (N'CajaMoneda',       N'18_AE4_Caja_Migraciones.sql'),
    (N'FacturaDetalle',   N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'PagoEvento',       N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'PedidoDetalleCompartido', N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'RecetaExtra',      N'21_AE4_Extras_Migraciones.sql'),
    (N'PedidoDetalleExtra', N'21_AE4_Extras_Migraciones.sql')
) AS t (Nombre, Script);

INSERT @r (Chequeo, Estado, Detalle)
VALUES (N'Vista vw_StockInsumo', IIF(OBJECT_ID('dbo.vw_StockInsumo', 'V') IS NULL, 'FALTA', 'OK'), N'11_AE4_Stock_Insumos_Migraciones.sql');

-- ---------- columnas que agregan las migraciones ----------
INSERT @r (Chequeo, Estado, Detalle)
SELECT c.Tabla + N'.' + c.Columna, IIF(COL_LENGTH('dbo.' + c.Tabla, c.Columna) IS NULL, 'FALTA', 'OK'), c.Script
FROM (VALUES
    (N'Mesa',           N'Activa',                 N'02_AE4_Mesas_Migraciones.sql'),
    (N'Producto',       N'Descripcion',            N'03_AE4_Productos_Migraciones.sql'),
    (N'Producto',       N'TiempoEstimadoMin',      N'07_AE4_Tiempos_Migraciones.sql'),
    (N'PedidoCabecera', N'FechaHoraSolicitaCuenta',N'06_AE4_Cuenta_Migraciones.sql'),
    (N'PedidoCabecera', N'IdJornada',              N'08_AE4_Jornada_Migraciones.sql'),
    (N'Producto',       N'Disponible',             N'10_AE4_Disponibilidad_Migraciones.sql'),
    (N'Producto',       N'AgotadoManual',          N'10_AE4_Disponibilidad_Migraciones.sql'),
    (N'Producto',       N'IdReceta',               N'12_AE4_Recetas_Migraciones.sql'),
    (N'ComandaRecibida',N'Estado',                 N'12_AE4_Recetas_Migraciones.sql'),
    (N'MovimientoStock',N'IdPerdida',              N'13_AE4_Perdidas_Migraciones.sql'),
    (N'RecetaIngrediente',N'EsQuitable',           N'14_AE4_Modificadores_Migraciones.sql'),
    (N'Receta',         N'IdInsumoProducido',      N'15_AE4_Elaboraciones_Vencimientos_Migraciones.sql'),
    (N'Receta',         N'Rinde',                  N'15_AE4_Elaboraciones_Vencimientos_Migraciones.sql'),
    (N'Receta',         N'DiasVencimiento',        N'15_AE4_Elaboraciones_Vencimientos_Migraciones.sql'),
    (N'MovimientoStock',N'IdProduccion',           N'15_AE4_Elaboraciones_Vencimientos_Migraciones.sql'),
    (N'Insumo',         N'DiasAvisoVencimiento',   N'16_AE4_Aviso_Vencimiento_Por_Insumo_Migraciones.sql'),
    (N'CotizacionMoneda',N'Fuente',                N'17_AE4_Cotizacion_Migraciones.sql'),
    (N'CotizacionMoneda',N'FechaHora',             N'17_AE4_Cotizacion_Migraciones.sql'),
    (N'MovimientoCaja', N'Moneda',                 N'18_AE4_Caja_Migraciones.sql'),
    (N'MovimientoCaja', N'Cotizacion',             N'18_AE4_Caja_Migraciones.sql'),
    (N'MovimientoCaja', N'MontoARS',               N'18_AE4_Caja_Migraciones.sql'),
    (N'MovimientoCaja', N'Concepto',               N'18_AE4_Caja_Migraciones.sql'),
    (N'MovimientoCaja', N'Medio',                  N'18_AE4_Caja_Migraciones.sql'),
    (N'CajaMoneda',     N'Medio',                  N'18_AE4_Caja_Migraciones.sql'),
    (N'Caja',           N'TotalEsperadoARS',       N'18_AE4_Caja_Migraciones.sql'),
    (N'Factura',        N'Estado',                 N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'Factura',        N'CotizacionUSD',          N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'Factura',        N'IdEmpleado',             N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'Pago',           N'Estado',                 N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'Pago',           N'Moneda',                 N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'Pago',           N'MontoPropina',           N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'Pago',           N'IdEmpleadoPropina',      N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'Pago',           N'ClaveIdempotencia',      N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'PedidoCabecera', N'CierreForzado',          N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'PedidoCabecera', N'IdEmpleadoCierre',       N'19_AE4_Cuenta_Pagos_Migraciones.sql'),
    (N'Pago',           N'MpPreferenciaId',        N'20_AE4_MercadoPago_Migraciones.sql'),
    (N'Pago',           N'MpUrlPago',              N'20_AE4_MercadoPago_Migraciones.sql'),
    (N'Pago',           N'FechaHoraExpiracion',    N'20_AE4_MercadoPago_Migraciones.sql'),
    (N'Pago',           N'MpPagoId',               N'20_AE4_MercadoPago_Migraciones.sql'),
    (N'Pago',           N'MpEstado',               N'20_AE4_MercadoPago_Migraciones.sql'),
    (N'Pago',           N'MpMontoNeto',            N'20_AE4_MercadoPago_Migraciones.sql'),
    (N'Factura',        N'NombreFactura',          N'22_AE4_Comprobante_Auditoria_Migraciones.sql')
) AS c (Tabla, Columna, Script)
WHERE OBJECT_ID('dbo.' + c.Tabla, 'U') IS NOT NULL;

-- ---------- datos base (solo si la tabla existe) ----------
DECLARE @n INT;

IF OBJECT_ID('dbo.Turno', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Turno WHERE Activo = 1', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: turnos activos', IIF(@n >= 1, 'OK', 'FALTA'), CONCAT(@n, N' (los carga 08_AE4_Jornada_Migraciones.sql)'));
END;

IF OBJECT_ID('dbo.Mesa', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Mesa', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: mesas', IIF(@n >= 1, 'OK', 'FALTA'), CONCAT(@n, N' (las carga 99_Seed_AE4.sql)'));
END;

IF OBJECT_ID('dbo.Rol', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Rol', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: roles', IIF(@n >= 4, 'OK', 'FALTA'), CONCAT(@n, N' (4 esperados; los carga 99_Seed_AE4.sql)'));
END;

IF OBJECT_ID('dbo.Empleado', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Empleado', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: empleados', IIF(@n >= 1, 'OK', 'FALTA'), CONCAT(@n, N' (los carga 99_Seed_AE4.sql)'));
END;

IF OBJECT_ID('dbo.Producto', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Producto', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: productos', IIF(@n >= 1, 'OK', 'FALTA'), CONCAT(@n, N' (los carga 99_Seed_AE4.sql)'));
END;

IF OBJECT_ID('dbo.Configuracion', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Configuracion WHERE Clave = N''dias_aviso_vencimiento''', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: configuracion de dias de aviso de vencimiento', IIF(@n = 1, 'OK', 'FALTA'), CONCAT(@n, N' (la carga 15_AE4_Elaboraciones_Vencimientos_Migraciones.sql)'));
END;

IF OBJECT_ID('dbo.MetodoPago', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.MetodoPago WHERE Nombre IN (N''Efectivo'', N''MercadoPago'')', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: metodos de pago (Efectivo y MercadoPago)', IIF(@n = 2, 'OK', 'FALTA'), CONCAT(@n, N' de 2 (los carga 19_AE4_Cuenta_Pagos_Migraciones.sql)'));
END;

INSERT @r (Chequeo, Estado, Detalle)
SELECT i.Nombre, IIF(EXISTS (SELECT 1 FROM sys.indexes WHERE name = i.Nombre), 'OK', 'FALTA'), N'19_AE4_Cuenta_Pagos_Migraciones.sql'
FROM (VALUES (N'UQ_Factura_Vigente'), (N'UQ_Pago_Pendiente'), (N'UQ_Pago_Clave')) AS i (Nombre)
WHERE OBJECT_ID('dbo.Pago', 'U') IS NOT NULL AND OBJECT_ID('dbo.Factura', 'U') IS NOT NULL;

INSERT @r (Chequeo, Estado, Detalle)
SELECT i.Nombre, IIF(EXISTS (SELECT 1 FROM sys.indexes WHERE name = i.Nombre), 'OK', 'FALTA'), N'20_AE4_MercadoPago_Migraciones.sql'
FROM (VALUES (N'UQ_Pago_MpPagoId'), (N'IX_Pago_Estado')) AS i (Nombre)
WHERE OBJECT_ID('dbo.Pago', 'U') IS NOT NULL;

INSERT @r (Chequeo, Estado, Detalle)
SELECT i.Nombre, IIF(EXISTS (SELECT 1 FROM sys.indexes WHERE name = i.Nombre), 'OK', 'FALTA'), N'21_AE4_Extras_Migraciones.sql'
FROM (VALUES (N'UQ_RecetaExtra'), (N'UQ_PedidoDetalleExtra')) AS i (Nombre)
WHERE OBJECT_ID('dbo.RecetaExtra', 'U') IS NOT NULL AND OBJECT_ID('dbo.PedidoDetalleExtra', 'U') IS NOT NULL;

INSERT @r (Chequeo, Estado, Detalle)
SELECT i.Nombre, IIF(EXISTS (SELECT 1 FROM sys.indexes WHERE name = i.Nombre), 'OK', 'FALTA'), N'22_AE4_Comprobante_Auditoria_Migraciones.sql'
FROM (VALUES (N'IX_PagoEvento_FechaHora'), (N'IX_MovimientoCaja_FechaHora')) AS i (Nombre)
WHERE OBJECT_ID('dbo.PagoEvento', 'U') IS NOT NULL AND OBJECT_ID('dbo.MovimientoCaja', 'U') IS NOT NULL;

IF OBJECT_ID('dbo.MovimientoCaja', 'U') IS NOT NULL
    INSERT @r (Chequeo, Estado, Detalle)
    SELECT N'MovimientoCaja.IdEmpleado admite NULL', IIF(c.is_nullable = 1, 'OK', 'FALTA'), N'20_AE4_MercadoPago_Migraciones.sql'
    FROM sys.columns c WHERE c.object_id = OBJECT_ID('dbo.MovimientoCaja') AND c.name = 'IdEmpleado';

SELECT Chequeo, Estado, Detalle FROM @r ORDER BY Orden;

-- ---------- informativo: turnos y jornada abierta ----------
IF OBJECT_ID('dbo.Turno', 'U') IS NOT NULL
    SELECT Id, Nombre, HoraApertura, HoraCierre, Activo FROM dbo.Turno ORDER BY Id;

IF OBJECT_ID('dbo.Jornada', 'U') IS NOT NULL
    SELECT Id, IdTurno, Fecha, Estado, FechaHoraApertura FROM dbo.Jornada WHERE Estado = 'Abierta';
