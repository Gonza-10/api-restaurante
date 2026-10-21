USE RestauranteDB;
GO

-- Bug #1: cada item de un pedido queda ligado a la comanda que lo pidio.
-- Antes, PedidoDetalle solo conocia la sesion de la mesa (IdPedidoCabecera), y por eso
-- el tablero de cocina y el ticket PDF mostraban los items de TODAS las comandas de la sesion.
-- La columna es NULL-able: los items anteriores a este script no registran a que comanda pertenecen.

IF COL_LENGTH('dbo.PedidoDetalle', 'IdComandaRecibida') IS NULL
BEGIN
    ALTER TABLE PedidoDetalle ADD IdComandaRecibida INT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_PedidoDetalle_ComandaRecibida'
      AND parent_object_id = OBJECT_ID('dbo.PedidoDetalle')
)
BEGIN
    ALTER TABLE PedidoDetalle
        ADD CONSTRAINT FK_PedidoDetalle_ComandaRecibida
        FOREIGN KEY (IdComandaRecibida) REFERENCES ComandaRecibida (Id);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_PedidoDetalle_ComandaRecibida'
      AND object_id = OBJECT_ID('dbo.PedidoDetalle')
)
BEGIN
    CREATE INDEX IX_PedidoDetalle_ComandaRecibida
    ON PedidoDetalle (IdComandaRecibida);
END
GO

-- Datos anteriores: solo se ligan los items de las sesiones que tienen UNA sola comanda,
-- porque ahi no hay ambiguedad. En las sesiones con varias comandas no se puede saber
-- que item pertenece a cual, asi que quedan en NULL. No se borra nada.
-- Es idempotente: solo toca los items que todavia estan en NULL.
UPDATE d
SET d.IdComandaRecibida = u.IdComanda
FROM PedidoDetalle d
INNER JOIN (
    SELECT IdPedidoCabecera, MIN(Id) AS IdComanda
    FROM ComandaRecibida
    GROUP BY IdPedidoCabecera
    HAVING COUNT(*) = 1
) u ON u.IdPedidoCabecera = d.IdPedidoCabecera
WHERE d.IdComandaRecibida IS NULL;
GO
