USE RestauranteDB;
GO

-- Cobros, hito 2: caja con arqueo por moneda y por medio de pago.
--
-- Reglas:
--   * Hay UNA sola caja abierta a la vez (lo garantiza un indice unico filtrado, igual que UQ_Jornada_Abierta).
--   * Abren y cierran Admin y Gerente. Se puede abrir y cerrar con la jornada cerrada.
--   * Todo pago necesita la caja abierta (eso se chequea en el hito 3, al emitir la factura).
--   * El arqueo tiene DOS medios:
--       - Efectivo: lo que hay en el cajon, por moneda (ARS, USD, BRL, PYG).
--       - MercadoPago: el dinero digital. No esta en el cajon: esta en la cuenta del restaurante. Cada cobro de Mercado Pago
--         APROBADO se anota en la caja con la etiqueta MercadoPago (siempre en pesos). Al cerrar, se declara lo que figura
--         acreditado en la cuenta de Mercado Pago y se compara con lo que el sistema registro.
--   * Esperado de efectivo en una moneda = apertura + ingresos - egresos. Esperado de Mercado Pago = ingresos - egresos
--     del periodo de la caja. Al cerrar se guarda la diferencia (declarado - esperado): no impide cerrar, queda registrada.
--   * Al cerrar tambien se guarda el total en pesos (efectivo convertido con la cotizacion vigente + Mercado Pago).
--
--   Caja.MontoApertura / MontoCierre -> el efectivo en PESOS (se mantienen por compatibilidad; el detalle esta en CajaMoneda).
--   Caja.TotalEsperadoARS / TotalDeclaradoARS -> efectivo (en pesos) + Mercado Pago, esperado y contado, al cerrar.
--   CajaMoneda    -> una fila por medio y moneda y por caja: apertura, esperado al cerrar, declarado y diferencia.
--   MovimientoCaja.Medio    -> Efectivo | MercadoPago (Mercado Pago solo existe en pesos).
--   MovimientoCaja.Moneda / Cotizacion / MontoARS -> moneda del movimiento, cotizacion vigente en ese momento
--                              (ARS por 1 unidad; 1 si es ARS) y su equivalente en pesos.
--   MovimientoCaja.Tipo     -> Ingreso | Egreso.
--   MovimientoCaja.Concepto -> Manual (lo carga Admin/Gerente), Venta (cobro), Propina (la propina queda en la caja como
--                              ingreso: en efectivo en el cajon, con Mercado Pago en la cuenta digital), Vuelto (egreso en
--                              pesos) y Anulacion (contramovimiento al anular un pago en efectivo).
--
-- Es idempotente: se puede ejecutar mas de una vez (tambien sobre una base que ya tenia la version anterior de este
-- script). Requiere el 00 y el 17.

-- ---------- Caja ----------
IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.Caja') AND name = 'MontoApertura' AND (precision <> 14 OR scale <> 2)
)
    ALTER TABLE dbo.Caja ALTER COLUMN MontoApertura DECIMAL(14,2) NOT NULL;
GO

IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.Caja') AND name = 'MontoCierre' AND (precision <> 14 OR scale <> 2)
)
    ALTER TABLE dbo.Caja ALTER COLUMN MontoCierre DECIMAL(14,2) NULL;
GO

IF COL_LENGTH('dbo.Caja', 'TotalEsperadoARS') IS NULL
    ALTER TABLE dbo.Caja ADD TotalEsperadoARS DECIMAL(14,2) NULL;
GO

IF COL_LENGTH('dbo.Caja', 'TotalDeclaradoARS') IS NULL
    ALTER TABLE dbo.Caja ADD TotalDeclaradoARS DECIMAL(14,2) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Caja_Estado')
    ALTER TABLE dbo.Caja ADD CONSTRAINT CK_Caja_Estado CHECK (Estado IN (N'Abierta', N'Cerrada'));
GO

-- Una sola caja abierta a la vez (lo garantiza la base, no solo la API)
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UQ_Caja_Abierta' AND object_id = OBJECT_ID('dbo.Caja')
)
    CREATE UNIQUE INDEX UQ_Caja_Abierta ON dbo.Caja (Estado) WHERE Estado = N'Abierta';
GO

-- ---------- CajaMoneda ----------
IF OBJECT_ID('dbo.CajaMoneda', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CajaMoneda (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_CajaMoneda PRIMARY KEY,
        IdCaja INT NOT NULL
            CONSTRAINT FK_CajaMoneda_Caja FOREIGN KEY REFERENCES dbo.Caja (Id),
        Medio NVARCHAR(20) NOT NULL CONSTRAINT DF_CajaMoneda_Medio DEFAULT N'Efectivo',
        Moneda NVARCHAR(3) NOT NULL,
        MontoApertura DECIMAL(14,2) NOT NULL CONSTRAINT DF_CajaMoneda_Apertura DEFAULT 0,
        MontoEsperado DECIMAL(14,2) NULL,    -- lo que tenia que haber al cerrar (se guarda al cerrar)
        MontoDeclarado DECIMAL(14,2) NULL,   -- lo que se conto (efectivo) o lo acreditado (Mercado Pago) al cerrar
        Diferencia DECIMAL(14,2) NULL,       -- declarado - esperado (negativo = faltante, positivo = sobrante)
        CONSTRAINT CK_CajaMoneda_Moneda CHECK (Moneda IN (N'ARS', N'USD', N'BRL', N'PYG')),
        CONSTRAINT CK_CajaMoneda_Montos CHECK (MontoApertura >= 0 AND (MontoDeclarado IS NULL OR MontoDeclarado >= 0))
    );
END
GO

-- Medio (para bases que ya tenian la tabla sin esa columna)
IF COL_LENGTH('dbo.CajaMoneda', 'Medio') IS NULL
    ALTER TABLE dbo.CajaMoneda ADD Medio NVARCHAR(20) NOT NULL CONSTRAINT DF_CajaMoneda_Medio DEFAULT N'Efectivo';
GO

-- La unicidad pasa a ser (caja, medio, moneda); la version anterior era (caja, moneda)
IF EXISTS (
    SELECT 1 FROM sys.key_constraints k
    WHERE k.name = 'UQ_CajaMoneda' AND k.parent_object_id = OBJECT_ID('dbo.CajaMoneda')
      AND NOT EXISTS (
          SELECT 1 FROM sys.index_columns ic
          JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
          WHERE ic.object_id = k.parent_object_id AND ic.index_id = k.unique_index_id AND c.name = 'Medio'
      )
)
    ALTER TABLE dbo.CajaMoneda DROP CONSTRAINT UQ_CajaMoneda;
GO

IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_CajaMoneda' AND parent_object_id = OBJECT_ID('dbo.CajaMoneda'))
    ALTER TABLE dbo.CajaMoneda ADD CONSTRAINT UQ_CajaMoneda UNIQUE (IdCaja, Medio, Moneda);
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_CajaMoneda_Medio')
    ALTER TABLE dbo.CajaMoneda ADD CONSTRAINT CK_CajaMoneda_Medio
        CHECK (Medio IN (N'Efectivo', N'MercadoPago') AND (Medio = N'Efectivo' OR Moneda = N'ARS'));
GO

-- ---------- MovimientoCaja ----------
IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.MovimientoCaja') AND name = 'Monto' AND (precision <> 14 OR scale <> 2)
)
    ALTER TABLE dbo.MovimientoCaja ALTER COLUMN Monto DECIMAL(14,2) NOT NULL;
GO

IF COL_LENGTH('dbo.MovimientoCaja', 'Moneda') IS NULL
    ALTER TABLE dbo.MovimientoCaja
        ADD Moneda NVARCHAR(3) NOT NULL CONSTRAINT DF_MovimientoCaja_Moneda DEFAULT N'ARS';
GO

IF COL_LENGTH('dbo.MovimientoCaja', 'Cotizacion') IS NULL
    ALTER TABLE dbo.MovimientoCaja
        ADD Cotizacion DECIMAL(18,8) NOT NULL CONSTRAINT DF_MovimientoCaja_Cotizacion DEFAULT 1;
GO

IF COL_LENGTH('dbo.MovimientoCaja', 'MontoARS') IS NULL
    ALTER TABLE dbo.MovimientoCaja ADD MontoARS DECIMAL(14,2) NULL;
GO

-- en las filas que ya existieran, el equivalente en pesos es el monto mismo
UPDATE dbo.MovimientoCaja SET MontoARS = Monto WHERE MontoARS IS NULL;
GO

IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.MovimientoCaja') AND name = 'MontoARS' AND is_nullable = 1)
    ALTER TABLE dbo.MovimientoCaja ALTER COLUMN MontoARS DECIMAL(14,2) NOT NULL;
GO

IF COL_LENGTH('dbo.MovimientoCaja', 'Concepto') IS NULL
    ALTER TABLE dbo.MovimientoCaja
        ADD Concepto NVARCHAR(20) NOT NULL CONSTRAINT DF_MovimientoCaja_Concepto DEFAULT N'Manual';
GO

IF COL_LENGTH('dbo.MovimientoCaja', 'Medio') IS NULL
    ALTER TABLE dbo.MovimientoCaja
        ADD Medio NVARCHAR(20) NOT NULL CONSTRAINT DF_MovimientoCaja_Medio DEFAULT N'Efectivo';
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_MovimientoCaja_Tipo')
    ALTER TABLE dbo.MovimientoCaja ADD CONSTRAINT CK_MovimientoCaja_Tipo CHECK (Tipo IN (N'Ingreso', N'Egreso'));
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_MovimientoCaja_Concepto')
    ALTER TABLE dbo.MovimientoCaja ADD CONSTRAINT CK_MovimientoCaja_Concepto
        CHECK (Concepto IN (N'Manual', N'Venta', N'Propina', N'Vuelto', N'Anulacion'));
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_MovimientoCaja_Moneda')
    ALTER TABLE dbo.MovimientoCaja ADD CONSTRAINT CK_MovimientoCaja_Moneda CHECK (Moneda IN (N'ARS', N'USD', N'BRL', N'PYG'));
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_MovimientoCaja_Montos')
    ALTER TABLE dbo.MovimientoCaja ADD CONSTRAINT CK_MovimientoCaja_Montos CHECK (Monto > 0 AND Cotizacion > 0 AND MontoARS >= 0);
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_MovimientoCaja_Medio')
    ALTER TABLE dbo.MovimientoCaja ADD CONSTRAINT CK_MovimientoCaja_Medio
        CHECK (Medio IN (N'Efectivo', N'MercadoPago') AND (Medio = N'Efectivo' OR Moneda = N'ARS'));
GO

-- Para sumar rapido los movimientos de una caja por medio y moneda (se rehace si venia sin Medio)
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_MovimientoCaja_Caja_Moneda' AND object_id = OBJECT_ID('dbo.MovimientoCaja'))
   AND NOT EXISTS (
       SELECT 1 FROM sys.index_columns ic
       JOIN sys.indexes i ON i.object_id = ic.object_id AND i.index_id = ic.index_id
       JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
       WHERE i.name = 'IX_MovimientoCaja_Caja_Moneda' AND i.object_id = OBJECT_ID('dbo.MovimientoCaja') AND c.name = 'Medio'
   )
    DROP INDEX IX_MovimientoCaja_Caja_Moneda ON dbo.MovimientoCaja;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_MovimientoCaja_Caja_Moneda' AND object_id = OBJECT_ID('dbo.MovimientoCaja')
)
    CREATE INDEX IX_MovimientoCaja_Caja_Moneda ON dbo.MovimientoCaja (IdCaja, Medio, Moneda) INCLUDE (Tipo, Monto, Concepto);
GO
