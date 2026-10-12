USE RestauranteDB;
GO

IF OBJECT_ID('dbo.ComandaRecibida', 'U') IS NULL
BEGIN
    CREATE TABLE ComandaRecibida (
        Id                 INT IDENTITY(1,1) NOT NULL,
        IdComandaUuid      UNIQUEIDENTIFIER  NOT NULL,
        IdPedidoCabecera   INT               NOT NULL,
        FechaHoraRecepcion DATETIME          NOT NULL CONSTRAINT DF_ComandaRecibida_Fecha DEFAULT (GETDATE()),

        CONSTRAINT PK_ComandaRecibida PRIMARY KEY (Id),
        CONSTRAINT UQ_ComandaRecibida_Uuid UNIQUE (IdComandaUuid),
        CONSTRAINT FK_ComandaRecibida_PedidoCabecera
            FOREIGN KEY (IdPedidoCabecera) REFERENCES PedidoCabecera (Id)
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UQ_PedidoCabecera_MesaAbierta'
      AND object_id = OBJECT_ID('dbo.PedidoCabecera')
)
BEGIN
    CREATE UNIQUE INDEX UQ_PedidoCabecera_MesaAbierta
    ON PedidoCabecera (IdMesa)
    WHERE Estado = 'Abierto';
END
GO