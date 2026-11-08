USE RestauranteDB;
GO

-- Cobros, hito 3: cuenta (Factura), pagos en efectivo, propina, vuelto y cierre de mesa.
--
--   MetodoPago     -> solo dos: Efectivo y MercadoPago.
--   Factura        -> la cuenta interna de una sesion de mesa (sin ARCA). UNA vigente por sesion (UQ_Factura_Vigente).
--                     Se emite al empezar a cobrar y congela el total y los renglones. Estado: Emitida | Pagada | Anulada.
--                     TotalUSD/BRL/PYG son la "foto" de cuanto equivale el total con la cotizacion de ese momento (tambien
--                     si se paga con Mercado Pago); quedan NULL solo si todavia no hay ninguna cotizacion guardada.
--   FacturaDetalle -> los renglones de la factura (copia de lo consumido, con el nombre del plato de ese momento).
--   Pago           -> una parte del cobro. Monto = lo que descuenta de la cuenta (en pesos). Estado: Pendiente | Aprobado |
--                     Rechazado | Cancelado | Expirado | Anulado. El efectivo nace Aprobado; solo el efectivo se anula.
--                     Moneda/MontoRecibido/Cotizacion: lo que entrego el cliente y a que cotizacion se tomo (un pago, una
--                     moneda). MontoPropina: propina en pesos (va solo al mozo de la mesa: IdEmpleadoPropina). Vuelto: siempre
--                     en pesos. Solo puede haber UN pago Pendiente por factura (UQ_Pago_Pendiente).
--                     ClaveIdempotencia: si el cliente reintenta el mismo cobro, no se duplica.
--   PagoEvento     -> historial de cada pago (auditoria): quien, cuando y que cambio.
--   PedidoDetalleCompartido -> plato dividido: los participantes entre los que se reparte el renglon en partes iguales.
--   PedidoCabecera.CierreForzado / MotivoCierre / IdEmpleadoCierre -> una mesa se puede cerrar con saldo pendiente solo
--                     por Admin/Gerente, con motivo; queda registrado.
--
-- Una mesa "en sobremesa" (cuenta pagada pero con gente sentada) no tiene columna propia: es una sesion Abierta con la
-- Factura Pagada. La mesa se libera cuando el mozo cierra la sesion.
-- Es idempotente: se puede ejecutar mas de una vez. Requiere el 00, el 17 y el 18.

-- ---------- MetodoPago ----------
IF NOT EXISTS (SELECT 1 FROM dbo.MetodoPago WHERE Nombre = N'Efectivo')
    INSERT INTO dbo.MetodoPago (Nombre) VALUES (N'Efectivo');
IF NOT EXISTS (SELECT 1 FROM dbo.MetodoPago WHERE Nombre = N'MercadoPago')
    INSERT INTO dbo.MetodoPago (Nombre) VALUES (N'MercadoPago');
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_MetodoPago_Nombre' AND object_id = OBJECT_ID('dbo.MetodoPago'))
    CREATE UNIQUE INDEX UQ_MetodoPago_Nombre ON dbo.MetodoPago (Nombre);
GO

-- ---------- Factura ----------
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.Factura') AND name = 'Total' AND (precision <> 14 OR scale <> 2))
    ALTER TABLE dbo.Factura ALTER COLUMN Total DECIMAL(14,2) NOT NULL;
GO
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.Factura') AND name = 'TotalUSD' AND (precision <> 14 OR scale <> 2 OR is_nullable = 0))
    ALTER TABLE dbo.Factura ALTER COLUMN TotalUSD DECIMAL(14,2) NULL;
GO
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.Factura') AND name = 'TotalBRL' AND (precision <> 14 OR scale <> 2 OR is_nullable = 0))
    ALTER TABLE dbo.Factura ALTER COLUMN TotalBRL DECIMAL(14,2) NULL;
GO
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.Factura') AND name = 'TotalPYG' AND (precision <> 14 OR scale <> 2 OR is_nullable = 0))
    ALTER TABLE dbo.Factura ALTER COLUMN TotalPYG DECIMAL(14,2) NULL;
GO
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.Factura') AND name = 'CambioEntregado' AND (precision <> 14 OR scale <> 2))
    ALTER TABLE dbo.Factura ALTER COLUMN CambioEntregado DECIMAL(14,2) NULL;
GO

IF COL_LENGTH('dbo.Factura', 'Estado') IS NULL
    ALTER TABLE dbo.Factura ADD Estado NVARCHAR(10) NOT NULL CONSTRAINT DF_Factura_Estado DEFAULT N'Emitida';
GO
IF COL_LENGTH('dbo.Factura', 'FechaHoraPago') IS NULL
    ALTER TABLE dbo.Factura ADD FechaHoraPago DATETIME NULL;
GO
IF COL_LENGTH('dbo.Factura', 'IdEmpleado') IS NULL
    ALTER TABLE dbo.Factura ADD IdEmpleado INT NULL CONSTRAINT FK_Factura_Empleado FOREIGN KEY REFERENCES dbo.Empleado (Id);
GO
IF COL_LENGTH('dbo.Factura', 'CotizacionUSD') IS NULL
    ALTER TABLE dbo.Factura ADD CotizacionUSD DECIMAL(18,8) NULL, CotizacionBRL DECIMAL(18,8) NULL, CotizacionPYG DECIMAL(18,8) NULL;
GO
IF COL_LENGTH('dbo.Factura', 'FechaHoraAnulacion') IS NULL
    ALTER TABLE dbo.Factura ADD FechaHoraAnulacion DATETIME NULL,
        IdEmpleadoAnulacion INT NULL CONSTRAINT FK_Factura_EmpleadoAnulacion FOREIGN KEY REFERENCES dbo.Empleado (Id),
        MotivoAnulacion NVARCHAR(200) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Factura_Estado')
    ALTER TABLE dbo.Factura ADD CONSTRAINT CK_Factura_Estado CHECK (Estado IN (N'Emitida', N'Pagada', N'Anulada'));
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Factura_Total')
    ALTER TABLE dbo.Factura ADD CONSTRAINT CK_Factura_Total CHECK (Total > 0);
GO

-- una sola factura vigente (no anulada) por sesion de mesa
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_Factura_Vigente' AND object_id = OBJECT_ID('dbo.Factura'))
    CREATE UNIQUE INDEX UQ_Factura_Vigente ON dbo.Factura (IdPedidoCabecera) WHERE Estado IN (N'Emitida', N'Pagada');
GO

-- ---------- FacturaDetalle ----------
IF OBJECT_ID('dbo.FacturaDetalle', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FacturaDetalle (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_FacturaDetalle PRIMARY KEY,
        IdFactura INT NOT NULL
            CONSTRAINT FK_FacturaDetalle_Factura FOREIGN KEY REFERENCES dbo.Factura (Id),
        IdPedidoDetalle INT NULL
            CONSTRAINT FK_FacturaDetalle_PedidoDetalle FOREIGN KEY REFERENCES dbo.PedidoDetalle (Id),
        IdProducto INT NOT NULL
            CONSTRAINT FK_FacturaDetalle_Producto FOREIGN KEY REFERENCES dbo.Producto (Id),
        Descripcion NVARCHAR(150) NOT NULL,       -- nombre del plato (y "sin ...") tal como se vendio
        Cantidad INT NOT NULL,
        PrecioUnitario DECIMAL(10,2) NOT NULL,
        SubTotal DECIMAL(10,2) NOT NULL,
        IdentificadorComensal NVARCHAR(50) NULL,
        CONSTRAINT CK_FacturaDetalle_Montos CHECK (Cantidad > 0 AND PrecioUnitario >= 0 AND SubTotal >= 0)
    );
    CREATE INDEX IX_FacturaDetalle_Factura ON dbo.FacturaDetalle (IdFactura);
END
GO

-- ---------- Pago ----------
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.Pago') AND name = 'Monto' AND (precision <> 14 OR scale <> 2))
    ALTER TABLE dbo.Pago ALTER COLUMN Monto DECIMAL(14,2) NOT NULL;
GO

IF COL_LENGTH('dbo.Pago', 'Estado') IS NULL
    ALTER TABLE dbo.Pago ADD Estado NVARCHAR(10) NOT NULL CONSTRAINT DF_Pago_Estado DEFAULT N'Aprobado';
GO
IF COL_LENGTH('dbo.Pago', 'Moneda') IS NULL
    ALTER TABLE dbo.Pago ADD Moneda NVARCHAR(3) NOT NULL CONSTRAINT DF_Pago_Moneda DEFAULT N'ARS';
GO
IF COL_LENGTH('dbo.Pago', 'MontoRecibido') IS NULL
    ALTER TABLE dbo.Pago ADD MontoRecibido DECIMAL(14,2) NULL;
GO
IF COL_LENGTH('dbo.Pago', 'Cotizacion') IS NULL
    ALTER TABLE dbo.Pago ADD Cotizacion DECIMAL(18,8) NOT NULL CONSTRAINT DF_Pago_Cotizacion DEFAULT 1;
GO
IF COL_LENGTH('dbo.Pago', 'MontoPropina') IS NULL
    ALTER TABLE dbo.Pago ADD MontoPropina DECIMAL(14,2) NOT NULL CONSTRAINT DF_Pago_Propina DEFAULT 0;
GO
IF COL_LENGTH('dbo.Pago', 'Vuelto') IS NULL
    ALTER TABLE dbo.Pago ADD Vuelto DECIMAL(14,2) NOT NULL CONSTRAINT DF_Pago_Vuelto DEFAULT 0;
GO
IF COL_LENGTH('dbo.Pago', 'IdEmpleado') IS NULL
    ALTER TABLE dbo.Pago ADD IdEmpleado INT NULL CONSTRAINT FK_Pago_Empleado FOREIGN KEY REFERENCES dbo.Empleado (Id);
GO
IF COL_LENGTH('dbo.Pago', 'IdEmpleadoPropina') IS NULL
    ALTER TABLE dbo.Pago ADD IdEmpleadoPropina INT NULL CONSTRAINT FK_Pago_EmpleadoPropina FOREIGN KEY REFERENCES dbo.Empleado (Id);
GO
IF COL_LENGTH('dbo.Pago', 'ClaveIdempotencia') IS NULL
    ALTER TABLE dbo.Pago ADD ClaveIdempotencia NVARCHAR(36) NULL;
GO
IF COL_LENGTH('dbo.Pago', 'FechaHoraAnulacion') IS NULL
    ALTER TABLE dbo.Pago ADD FechaHoraAnulacion DATETIME NULL,
        IdEmpleadoAnulacion INT NULL CONSTRAINT FK_Pago_EmpleadoAnulacion FOREIGN KEY REFERENCES dbo.Empleado (Id),
        MotivoAnulacion NVARCHAR(200) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Pago_Estado')
    ALTER TABLE dbo.Pago ADD CONSTRAINT CK_Pago_Estado
        CHECK (Estado IN (N'Pendiente', N'Aprobado', N'Rechazado', N'Cancelado', N'Expirado', N'Anulado'));
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Pago_Moneda')
    ALTER TABLE dbo.Pago ADD CONSTRAINT CK_Pago_Moneda CHECK (Moneda IN (N'ARS', N'USD', N'BRL', N'PYG'));
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Pago_Montos')
    ALTER TABLE dbo.Pago ADD CONSTRAINT CK_Pago_Montos
        CHECK (Monto >= 0 AND MontoPropina >= 0 AND Vuelto >= 0 AND Cotizacion > 0 AND Monto + MontoPropina > 0);
GO

-- un solo pago pendiente por factura: evita cobrar dos veces lo mismo
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_Pago_Pendiente' AND object_id = OBJECT_ID('dbo.Pago'))
    CREATE UNIQUE INDEX UQ_Pago_Pendiente ON dbo.Pago (IdFactura) WHERE Estado = N'Pendiente';
GO
-- un reintento con la misma clave no genera otro pago
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_Pago_Clave' AND object_id = OBJECT_ID('dbo.Pago'))
    CREATE UNIQUE INDEX UQ_Pago_Clave ON dbo.Pago (ClaveIdempotencia) WHERE ClaveIdempotencia IS NOT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Pago_Factura' AND object_id = OBJECT_ID('dbo.Pago'))
    CREATE INDEX IX_Pago_Factura ON dbo.Pago (IdFactura) INCLUDE (Estado, Monto, MontoPropina);
GO

-- ---------- PagoEvento ----------
IF OBJECT_ID('dbo.PagoEvento', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PagoEvento (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_PagoEvento PRIMARY KEY,
        IdPago INT NOT NULL CONSTRAINT FK_PagoEvento_Pago FOREIGN KEY REFERENCES dbo.Pago (Id),
        FechaHora DATETIME NOT NULL CONSTRAINT DF_PagoEvento_FechaHora DEFAULT GETDATE(),
        Evento NVARCHAR(30) NOT NULL,            -- Creado, Aprobado, Anulado...
        EstadoAnterior NVARCHAR(10) NULL,
        EstadoNuevo NVARCHAR(10) NOT NULL,
        Detalle NVARCHAR(400) NULL,
        IdEmpleado INT NULL CONSTRAINT FK_PagoEvento_Empleado FOREIGN KEY REFERENCES dbo.Empleado (Id)
    );
    CREATE INDEX IX_PagoEvento_Pago ON dbo.PagoEvento (IdPago);
END
GO

-- ---------- PedidoDetalleCompartido ----------
IF OBJECT_ID('dbo.PedidoDetalleCompartido', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PedidoDetalleCompartido (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_PedidoDetalleCompartido PRIMARY KEY,
        IdPedidoDetalle INT NOT NULL
            CONSTRAINT FK_PedidoDetalleCompartido_Detalle FOREIGN KEY REFERENCES dbo.PedidoDetalle (Id) ON DELETE CASCADE,
        Participante NVARCHAR(50) NOT NULL,       -- nombre del comensal o "Usuario no registrado N"
        CONSTRAINT UQ_PedidoDetalleCompartido UNIQUE (IdPedidoDetalle, Participante)
    );
END
GO

-- ---------- PedidoCabecera: cierre de mesa ----------
IF COL_LENGTH('dbo.PedidoCabecera', 'CierreForzado') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD CierreForzado BIT NOT NULL CONSTRAINT DF_PedidoCabecera_CierreForzado DEFAULT 0;
GO
IF COL_LENGTH('dbo.PedidoCabecera', 'MotivoCierre') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD MotivoCierre NVARCHAR(200) NULL;
GO
IF COL_LENGTH('dbo.PedidoCabecera', 'IdEmpleadoCierre') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD IdEmpleadoCierre INT NULL CONSTRAINT FK_PedidoCabecera_EmpleadoCierre FOREIGN KEY REFERENCES dbo.Empleado (Id);
GO
