USE RestauranteDB;
GO

-- Cobros, hito 6: factura PDF a pedido del cliente y linea de tiempo de auditoria.
--
-- Factura.SolicitoTicket (ya existia desde el script 00, sin uso): ahora es la casilla "quiero factura" que el cliente (o el mozo)
--            marca antes de pagar. 1 = el cliente pidio el comprobante PDF. La factura interna se emite igual para poder cobrar;
--            lo opcional es el PDF.
-- Factura.NombreFactura (nueva): el nombre que figura en el comprobante y en el nombre del archivo ("David - 08-11-26.pdf").
--            NULL mientras nadie pidio el comprobante.
-- Indices por fecha: la linea de tiempo de auditoria (GET /auditoria) filtra por rango de fechas en PagoEvento y MovimientoCaja.
--
-- Requiere el 19 (Factura, Pago, PagoEvento) y el 18 (MovimientoCaja). Es idempotente: se puede ejecutar mas de una vez.

IF COL_LENGTH('dbo.Factura', 'NombreFactura') IS NULL
    ALTER TABLE dbo.Factura ADD NombreFactura NVARCHAR(100) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_PagoEvento_FechaHora' AND object_id = OBJECT_ID('dbo.PagoEvento'))
    CREATE INDEX IX_PagoEvento_FechaHora ON dbo.PagoEvento (FechaHora) INCLUDE (IdPago, Evento);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_MovimientoCaja_FechaHora' AND object_id = OBJECT_ID('dbo.MovimientoCaja'))
    CREATE INDEX IX_MovimientoCaja_FechaHora ON dbo.MovimientoCaja (FechaHora) INCLUDE (IdCaja, Concepto);
GO
PRINT 'Script 22 (comprobante y auditoria) aplicado.';
GO
