USE RestauranteDB;
GO

-- Pago con tarjeta de credito/debito (manual): no hay pasarela ni API. El cliente pide pagar con tarjeta, el mozo recibe el
-- aviso, lleva el postnet y, cuando el dinero impacta, CONFIRMA el cobro en el sistema (POST /facturas/{id}/pagos/tarjeta).
-- La tarjeta no mueve el arqueo del efectivo: no genera movimientos de caja.
--
-- MetodoPago: se agrega 'Tarjeta' (ya existian Efectivo y MercadoPago).
-- PedidoCabecera.MetodoPagoSolicitado (nueva): con que medio dijo el cliente que quiere pagar al pedir la cuenta
--            (Efectivo, MercadoPago o Tarjeta; NULL = no lo dijo). Es un aviso para el mozo: no obliga a pagar asi.
--
-- Requiere el 19 (MetodoPago). Es idempotente: se puede ejecutar mas de una vez.

IF NOT EXISTS (SELECT 1 FROM dbo.MetodoPago WHERE Nombre = N'Tarjeta')
    INSERT INTO dbo.MetodoPago (Nombre) VALUES (N'Tarjeta');
GO

IF COL_LENGTH('dbo.PedidoCabecera', 'MetodoPagoSolicitado') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD MetodoPagoSolicitado NVARCHAR(20) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_PedidoCabecera_MetodoPagoSolicitado')
    ALTER TABLE dbo.PedidoCabecera ADD CONSTRAINT CK_PedidoCabecera_MetodoPagoSolicitado
        CHECK (MetodoPagoSolicitado IS NULL OR MetodoPagoSolicitado IN (N'Efectivo', N'MercadoPago', N'Tarjeta'));
GO
PRINT 'Script 24 (pago con tarjeta) aplicado.';
GO
