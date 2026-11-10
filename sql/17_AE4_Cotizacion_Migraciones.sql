USE RestauranteDB;
GO

-- Cobros, hito 1: cotizacion oficial de las monedas (USD, BRL, PYG).
--
-- La cuenta siempre esta en pesos (ARS). Las cotizaciones se usan para cobrar efectivo en otra moneda y para mostrar
-- en la factura cuanto equivale el total en USD, BRL y PYG. Se actualizan SOLAS desde la API del BCRA (nadie las carga a
-- mano): el proceso worker_cotizacion.py consulta cada 30 minutos y guarda una fila nueva SOLO si el valor cambio.
-- La cotizacion vigente es la ultima fila de cada moneda; los fines de semana y feriados el BCRA no publica nada, asi
-- que sigue vigente la ultima guardada (respaldo).
--
--   CotizacionMoneda.Valor     -> ARS por 1 unidad de la moneda (tipoCotizacion del BCRA). DECIMAL(18,8): el guarani
--                                 vale ~0,2388 pesos y con 4 decimales se perderia precision al convertir montos grandes.
--   CotizacionMoneda.Fecha     -> fecha de la cotizacion segun la fuente (el dia habil al que corresponde).
--   CotizacionMoneda.FechaHora -> momento en que NOSOTROS la guardamos.
--   CotizacionMoneda.Fuente    -> de donde salio (BCRA).
--
-- La ultima consulta (exitosa y con error) se guarda en la tabla Configuracion (script 15), no aca.
-- Es idempotente: se puede ejecutar mas de una vez. Requiere el 00 (y el 15 para que la app guarde la ultima consulta).

-- ---------- Valor con 8 decimales ----------
IF EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.CotizacionMoneda') AND name = 'Valor' AND (precision <> 18 OR scale <> 8)
)
    ALTER TABLE dbo.CotizacionMoneda ALTER COLUMN Valor DECIMAL(18,8) NOT NULL;
GO

-- ---------- Fuente y FechaHora ----------
IF COL_LENGTH('dbo.CotizacionMoneda', 'Fuente') IS NULL
    ALTER TABLE dbo.CotizacionMoneda
        ADD Fuente NVARCHAR(30) NOT NULL CONSTRAINT DF_CotizacionMoneda_Fuente DEFAULT N'BCRA';
GO

IF COL_LENGTH('dbo.CotizacionMoneda', 'FechaHora') IS NULL
    ALTER TABLE dbo.CotizacionMoneda
        ADD FechaHora DATETIME NOT NULL CONSTRAINT DF_CotizacionMoneda_FechaHora DEFAULT GETDATE();
GO

-- ---------- Reglas de la base ----------
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_CotizacionMoneda_Moneda')
    ALTER TABLE dbo.CotizacionMoneda
        ADD CONSTRAINT CK_CotizacionMoneda_Moneda CHECK (Moneda IN (N'USD', N'BRL', N'PYG'));
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_CotizacionMoneda_Valor')
    ALTER TABLE dbo.CotizacionMoneda
        ADD CONSTRAINT CK_CotizacionMoneda_Valor CHECK (Valor > 0);
GO

-- Para buscar rapido la ultima cotizacion de cada moneda
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_CotizacionMoneda_Moneda_FechaHora' AND object_id = OBJECT_ID('dbo.CotizacionMoneda')
)
    CREATE INDEX IX_CotizacionMoneda_Moneda_FechaHora
        ON dbo.CotizacionMoneda (Moneda, FechaHora DESC, Id DESC)
        INCLUDE (Valor, Fecha, Fuente);
GO
