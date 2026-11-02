USE RestauranteDB;
GO

-- Stock, hito 4: perdidas con motivo.
--
-- Perdida -> una perdida registrada por el personal: que se perdio (un INSUMO suelto, o un PLATO ya cocinado),
--            cuanto, por que (motivo de una lista cerrada) y quien la cargo.
--            Alcance 'Insumo': IdInsumo y Cantidad en unidad base (g, ml o u).
--            Alcance 'Plato' : IdProducto y Cantidad en platos enteros; se descuentan los insumos de su receta.
--            El motivo es una lista cerrada para poder agrupar y saber donde y por que se pierde mas.
--            'otro' exige una nota que lo explique.
-- MovimientoStock.IdPerdida -> une cada movimiento del libro con la perdida que lo origino. Asi el VALOR de una
--            perdida se calcula con el costo real de los lotes de los que salio (FEFO): no se guarda ningun
--            precio aparte ni se usa un promedio general.
--
-- Es idempotente: se puede ejecutar mas de una vez.

-- ---------- Perdida ----------
IF OBJECT_ID('dbo.Perdida', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Perdida (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Perdida PRIMARY KEY,
        FechaHora DATETIME NOT NULL CONSTRAINT DF_Perdida_FechaHora DEFAULT GETDATE(),
        IdEmpleado INT NOT NULL CONSTRAINT FK_Perdida_Empleado FOREIGN KEY REFERENCES dbo.Empleado (Id),
        IdJornada INT NULL CONSTRAINT FK_Perdida_Jornada FOREIGN KEY REFERENCES dbo.Jornada (Id),
        Alcance NVARCHAR(10) NOT NULL,
        IdInsumo INT NULL CONSTRAINT FK_Perdida_Insumo FOREIGN KEY REFERENCES dbo.Insumo (Id),
        IdProducto INT NULL CONSTRAINT FK_Perdida_Producto FOREIGN KEY REFERENCES dbo.Producto (Id),
        Cantidad DECIMAL(12,3) NOT NULL,
        Motivo NVARCHAR(20) NOT NULL,
        Nota NVARCHAR(300) NULL,
        CONSTRAINT CK_Perdida_Alcance CHECK (Alcance IN (N'Insumo', N'Plato')),
        CONSTRAINT CK_Perdida_Que CHECK (
            (Alcance = N'Insumo' AND IdInsumo IS NOT NULL AND IdProducto IS NULL)
            OR (Alcance = N'Plato' AND IdProducto IS NOT NULL AND IdInsumo IS NULL)
        ),
        CONSTRAINT CK_Perdida_Cantidad CHECK (Cantidad > 0),
        CONSTRAINT CK_Perdida_Motivo CHECK (Motivo IN (
            N'vencimiento', N'rotura_derrame', N'error_cocina', N'devolucion_cliente', N'consumo_personal', N'otro'
        )),
        CONSTRAINT CK_Perdida_NotaOtro CHECK (Motivo <> N'otro' OR LEN(LTRIM(RTRIM(ISNULL(Nota, N'')))) > 0)
    );
    CREATE INDEX IX_Perdida_FechaHora ON dbo.Perdida (FechaHora);
    CREATE INDEX IX_Perdida_Motivo ON dbo.Perdida (Motivo);
END
GO

-- ---------- MovimientoStock.IdPerdida ----------
IF COL_LENGTH('dbo.MovimientoStock', 'IdPerdida') IS NULL
BEGIN
    ALTER TABLE dbo.MovimientoStock ADD IdPerdida INT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_MovimientoStock_Perdida' AND parent_object_id = OBJECT_ID('dbo.MovimientoStock')
)
BEGIN
    ALTER TABLE dbo.MovimientoStock
        ADD CONSTRAINT FK_MovimientoStock_Perdida FOREIGN KEY (IdPerdida) REFERENCES dbo.Perdida (Id);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE name = 'IX_MovimientoStock_Perdida' AND object_id = OBJECT_ID('dbo.MovimientoStock')
)
BEGIN
    CREATE INDEX IX_MovimientoStock_Perdida ON dbo.MovimientoStock (IdPerdida) WHERE IdPerdida IS NOT NULL;
END
GO
