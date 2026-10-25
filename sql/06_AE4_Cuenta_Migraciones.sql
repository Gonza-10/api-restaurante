USE RestauranteDB;
GO

-- Bug #4: el mozo tiene que poder ver cuando una mesa pide la cuenta.
-- Se guarda la hora en que el cliente la pidio (NULL = todavia no la pidio); con la hora se sabe
-- cuanto hace que esperan, y "solicita_cuenta" se calcula como "la fecha no es NULL".
-- Es idempotente: se puede ejecutar mas de una vez.

IF COL_LENGTH('dbo.PedidoCabecera', 'FechaHoraSolicitaCuenta') IS NULL
BEGIN
    ALTER TABLE PedidoCabecera ADD FechaHoraSolicitaCuenta DATETIME NULL;
END
GO
