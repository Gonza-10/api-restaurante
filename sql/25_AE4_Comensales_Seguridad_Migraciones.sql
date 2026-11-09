USE RestauranteDB;
GO

-- Comensales y seguridad de la mesa.
--
-- Modalidad de la mesa (la elige el mozo al abrir): Familiar (todos agregan al pedido, la cuenta va a nombre de una persona)
-- o Grupal (cada dispositivo escribe su nombre al entrar y se pide el OK de todos en la primera ronda).
--
-- PedidoCabecera (columnas nuevas):
--   Modalidad          Familiar / Grupal. Las sesiones anteriores quedan como Familiar.
--   RondaLiberada      1 = la primera ronda ya salio a cocina. En una mesa Familiar nace en 1 (no hay espera); en una Grupal
--                      nace en 0 y pasa a 1 cuando todos los comensales dan el OK o cuando el mozo la libera a mano.
--   PinRegeneradoEn / PinRegeneradoPor / AvisoPinPendiente   ultimo cambio de PIN, quien lo pidio y si el mozo todavia no vio
--                      el aviso (aviso urgente al mozo; lo confirma con POST /sesiones-mesa/{id}/pin/visto).
--   PinsAnteriores     PIN que tuvo la mesa antes de cada cambio (separados por coma). Sirve para decirle a un dispositivo con el
--                      PIN viejo "el PIN cambio, pedilo al mozo" sin contarlo como intento fallido (si no, un celular que sigue
--                      consultando con el PIN viejo bloquearia por IP a todos los de la mesa).
--
-- Comensal (tabla nueva): quien esta en la mesa. Nombre unico dentro de la sesion (sin distinguir mayusculas).
--   Estado             Activo / Retirado (se fue de la mesa: ya no pide ni cuenta para el OK de la primera ronda).
--   OkPrimeraRonda     1 = ya pidio todo lo que queria en la primera ronda ("nada mas por ahora" tambien cuenta).
--
-- ComandaRecibida (columnas nuevas y estado nuevo):
--   IdComensal         quien hizo el pedido (NULL en las comandas sin comensal).
--   Estado             se suma 'Cancelada' (se cancelo antes de prepararse: stock devuelto, sin renglones en la cuenta).
--   FechaHoraCancelacion  cuando se cancelo. El motivo queda en Motivo.
--
-- El stock de una comanda cancelada se devuelve con movimientos 'Devolucion' (el tipo ya existia en el libro de stock).
--
-- Requiere el 00 (PedidoCabecera), el 05 (ComandaRecibida) y el 12 (CK_ComandaRecibida_Estado). Es idempotente.

IF COL_LENGTH('dbo.PedidoCabecera', 'Modalidad') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD Modalidad NVARCHAR(10) NOT NULL
        CONSTRAINT DF_PedidoCabecera_Modalidad DEFAULT N'Familiar';
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_PedidoCabecera_Modalidad')
    ALTER TABLE dbo.PedidoCabecera ADD CONSTRAINT CK_PedidoCabecera_Modalidad CHECK (Modalidad IN (N'Familiar', N'Grupal'));
GO

-- las sesiones que ya existian: la ronda ya salio (se agrega con 1 y despues el valor por defecto pasa a 0 para las nuevas)
IF COL_LENGTH('dbo.PedidoCabecera', 'RondaLiberada') IS NULL
BEGIN
    ALTER TABLE dbo.PedidoCabecera ADD RondaLiberada BIT NOT NULL CONSTRAINT DF_PedidoCabecera_RondaLiberada DEFAULT 1;
    ALTER TABLE dbo.PedidoCabecera DROP CONSTRAINT DF_PedidoCabecera_RondaLiberada;
    ALTER TABLE dbo.PedidoCabecera ADD CONSTRAINT DF_PedidoCabecera_RondaLiberada DEFAULT 0 FOR RondaLiberada;
END
GO

IF COL_LENGTH('dbo.PedidoCabecera', 'PinRegeneradoEn') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD PinRegeneradoEn DATETIME NULL;
GO

IF COL_LENGTH('dbo.PedidoCabecera', 'PinRegeneradoPor') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD PinRegeneradoPor NVARCHAR(80) NULL;
GO

IF COL_LENGTH('dbo.PedidoCabecera', 'PinsAnteriores') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD PinsAnteriores NVARCHAR(60) NULL;
GO

IF COL_LENGTH('dbo.PedidoCabecera', 'AvisoPinPendiente') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD AvisoPinPendiente BIT NOT NULL CONSTRAINT DF_PedidoCabecera_AvisoPinPendiente DEFAULT 0;
GO

IF OBJECT_ID('dbo.Comensal', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Comensal (
        Id                 INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Comensal PRIMARY KEY,
        IdPedidoCabecera   INT NOT NULL CONSTRAINT FK_Comensal_PedidoCabecera REFERENCES dbo.PedidoCabecera(Id),
        Nombre             NVARCHAR(50) NOT NULL,
        FechaHoraIngreso   DATETIME NOT NULL CONSTRAINT DF_Comensal_Ingreso DEFAULT GETDATE(),
        Estado             NVARCHAR(10) NOT NULL CONSTRAINT DF_Comensal_Estado DEFAULT N'Activo',
        OkPrimeraRonda     BIT NOT NULL CONSTRAINT DF_Comensal_Ok DEFAULT 0,
        FechaHoraRetiro    DATETIME NULL,
        CONSTRAINT CK_Comensal_Estado CHECK (Estado IN (N'Activo', N'Retirado'))
    );
END
GO

-- nombre unico por sesion; la comparacion no distingue mayusculas ni acentos segun la intercalacion de la base
-- (Latin1_General_CI_AS), y el codigo igual lo controla antes de insertar
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_Comensal_Sesion_Nombre' AND object_id = OBJECT_ID('dbo.Comensal'))
    CREATE UNIQUE INDEX UQ_Comensal_Sesion_Nombre ON dbo.Comensal (IdPedidoCabecera, Nombre);
GO

IF COL_LENGTH('dbo.ComandaRecibida', 'IdComensal') IS NULL
    ALTER TABLE dbo.ComandaRecibida ADD IdComensal INT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_ComandaRecibida_Comensal')
    ALTER TABLE dbo.ComandaRecibida ADD CONSTRAINT FK_ComandaRecibida_Comensal FOREIGN KEY (IdComensal) REFERENCES dbo.Comensal(Id);
GO

IF COL_LENGTH('dbo.ComandaRecibida', 'FechaHoraCancelacion') IS NULL
    ALTER TABLE dbo.ComandaRecibida ADD FechaHoraCancelacion DATETIME NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ComandaRecibida_Comensal' AND object_id = OBJECT_ID('dbo.ComandaRecibida'))
    CREATE INDEX IX_ComandaRecibida_Comensal ON dbo.ComandaRecibida (IdComensal);
GO

-- el estado 'Cancelada' se suma a la restriccion (se recrea solo si todavia no la admite)
IF EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = 'CK_ComandaRecibida_Estado' AND parent_object_id = OBJECT_ID('dbo.ComandaRecibida')
      AND definition NOT LIKE N'%Cancelada%'
)
    ALTER TABLE dbo.ComandaRecibida DROP CONSTRAINT CK_ComandaRecibida_Estado;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = 'CK_ComandaRecibida_Estado' AND parent_object_id = OBJECT_ID('dbo.ComandaRecibida')
)
    ALTER TABLE dbo.ComandaRecibida ADD CONSTRAINT CK_ComandaRecibida_Estado
        CHECK (Estado IN (N'Aceptada', N'Rechazada', N'Cancelada'));
GO
PRINT 'Script 25 (comensales y seguridad de la mesa) aplicado.';
GO
