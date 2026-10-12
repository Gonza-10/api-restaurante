USE RestauranteDB;
GO

-- Una mesa no puede tener dos sesiones abiertas (ya existe desde AE2; se vuelve a asegurar aca)
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UQ_PedidoCabecera_MesaAbierta' AND object_id = OBJECT_ID('dbo.PedidoCabecera')
)
    CREATE UNIQUE INDEX UQ_PedidoCabecera_MesaAbierta ON dbo.PedidoCabecera (IdMesa) WHERE Estado = 'Abierto';
GO

-- Dos sesiones abiertas no pueden compartir PIN: el PIN identifica a la mesa
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UQ_PedidoCabecera_PinAbierto' AND object_id = OBJECT_ID('dbo.PedidoCabecera')
)
BEGIN
    IF EXISTS (SELECT CodigoPin FROM dbo.PedidoCabecera WHERE Estado = 'Abierto' GROUP BY CodigoPin HAVING COUNT(*) > 1)
        RAISERROR('Hay sesiones abiertas con el mismo PIN: cerrarlas antes de crear UQ_PedidoCabecera_PinAbierto.', 16, 1);
    ELSE
        CREATE UNIQUE INDEX UQ_PedidoCabecera_PinAbierto ON dbo.PedidoCabecera (CodigoPin) WHERE Estado = 'Abierto';
END
GO

-- Sincroniza Mesa.Estado con las sesiones: ocupada si y solo si tiene una sesion abierta
UPDATE m SET m.Estado = CASE WHEN EXISTS (
        SELECT 1 FROM dbo.PedidoCabecera p WHERE p.IdMesa = m.Id AND p.Estado = 'Abierto') THEN 1 ELSE 0 END
FROM dbo.Mesa m;
GO
