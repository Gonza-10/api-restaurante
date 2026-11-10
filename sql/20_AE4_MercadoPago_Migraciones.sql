-- =====================================================================================
-- AE4 - Cobros, hito 4: Mercado Pago (Checkout Pro con preferencias).
-- Requiere haber corrido antes el 00, el 18 y el 19. Se puede correr mas de una vez (idempotente).
--
-- Pago:
--   ReferenciaExterna  -> ya existia: aca guarda nuestra referencia 'SG-<id del pago>' (external_reference en Mercado Pago).
--   MpPreferenciaId    -> id de la preferencia (el link de pago) creada en Mercado Pago.
--   MpUrlPago          -> link al que se redirige al cliente para pagar.
--   FechaHoraExpiracion-> hasta cuando se puede pagar ese link. Despues el pago pendiente se marca Expirado.
--   MpPagoId           -> id del pago en Mercado Pago cuando se aprueba (UNIQUE: un pago de MP no se registra dos veces).
--   MpEstado           -> ultimo estado informado por Mercado Pago (approved, rejected, in_process...), solo informativo.
--   MpMontoNeto        -> lo que Mercado Pago acredita despues de su comision (informativo; la caja registra el bruto).
-- MovimientoCaja.IdEmpleado pasa a admitir NULL: una aprobacion de Mercado Pago la registra el sistema, no una persona.
-- =====================================================================================
SET QUOTED_IDENTIFIER ON;
GO

IF COL_LENGTH('dbo.Pago', 'MpPreferenciaId') IS NULL
    ALTER TABLE dbo.Pago ADD MpPreferenciaId NVARCHAR(100) NULL;
GO
IF COL_LENGTH('dbo.Pago', 'MpUrlPago') IS NULL
    ALTER TABLE dbo.Pago ADD MpUrlPago NVARCHAR(500) NULL;
GO
IF COL_LENGTH('dbo.Pago', 'FechaHoraExpiracion') IS NULL
    ALTER TABLE dbo.Pago ADD FechaHoraExpiracion DATETIME NULL;
GO
IF COL_LENGTH('dbo.Pago', 'MpPagoId') IS NULL
    ALTER TABLE dbo.Pago ADD MpPagoId NVARCHAR(40) NULL;
GO
IF COL_LENGTH('dbo.Pago', 'MpEstado') IS NULL
    ALTER TABLE dbo.Pago ADD MpEstado NVARCHAR(30) NULL;
GO
IF COL_LENGTH('dbo.Pago', 'MpMontoNeto') IS NULL
    ALTER TABLE dbo.Pago ADD MpMontoNeto DECIMAL(14,2) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_Pago_MpPagoId' AND object_id = OBJECT_ID('dbo.Pago'))
    CREATE UNIQUE INDEX UQ_Pago_MpPagoId ON dbo.Pago (MpPagoId) WHERE MpPagoId IS NOT NULL;
GO
-- el worker busca los pagos pendientes de Mercado Pago a cada rato
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Pago_Estado' AND object_id = OBJECT_ID('dbo.Pago'))
    CREATE INDEX IX_Pago_Estado ON dbo.Pago (Estado, FechaHora) INCLUDE (IdFactura, IdMetodoPago);
GO

-- un cobro aprobado por Mercado Pago lo anota el sistema: sin empleado
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.MovimientoCaja') AND name = 'IdEmpleado' AND is_nullable = 0)
    ALTER TABLE dbo.MovimientoCaja ALTER COLUMN IdEmpleado INT NULL;
GO
PRINT 'Script 20 (Mercado Pago) aplicado.';
GO
