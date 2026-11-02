USE RestauranteDB;
GO

-- Stock, hito 6: elaboraciones (sub-recetas con rinde), vencimientos y configuracion del stock.
--
-- Receta.IdInsumoProducido / Rinde / DiasVencimiento -> una receta puede ser una ELABORACION: cocinar un insumo propio
--            (salsa, masa, caldo) a partir de otros insumos. IdInsumoProducido es el insumo que sale; Rinde es cuanto
--            sale de UNA tanda (en la unidad base de ese insumo); DiasVencimiento es la vida util del lote producido.
--            Una elaboracion puede usar como ingrediente a otra elaboracion (la aplicacion impide los ciclos).
--            Un insumo tiene como maximo una receta de elaboracion (indice unico filtrado).
-- Produccion -> cada vez que Cocina elabora: que receta, cuantas tandas, cuanto salio, quien y cuando.
--            El costo del lote producido NO se guarda aparte: es lo que costaron los lotes que se consumieron (costo real)
--            dividido lo que salio, y queda en LoteInsumo.CostoUnitario.
-- MovimientoStock.IdProduccion -> une los movimientos del libro (los consumos de los ingredientes y el ingreso del
--            lote producido) con la produccion que los origino.
-- Configuracion -> parametros del stock que Admin y Gerente pueden cambiar (por ahora: dias de aviso de vencimiento).
--
-- Es idempotente: se puede ejecutar mas de una vez.

-- ---------- Receta: columnas de elaboracion ----------
IF COL_LENGTH('dbo.Receta', 'IdInsumoProducido') IS NULL
BEGIN
    ALTER TABLE dbo.Receta ADD IdInsumoProducido INT NULL;
END
GO

IF COL_LENGTH('dbo.Receta', 'Rinde') IS NULL
BEGIN
    ALTER TABLE dbo.Receta ADD Rinde DECIMAL(12,3) NULL;
END
GO

IF COL_LENGTH('dbo.Receta', 'DiasVencimiento') IS NULL
BEGIN
    ALTER TABLE dbo.Receta ADD DiasVencimiento INT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_Receta_InsumoProducido' AND parent_object_id = OBJECT_ID('dbo.Receta')
)
BEGIN
    ALTER TABLE dbo.Receta
        ADD CONSTRAINT FK_Receta_InsumoProducido FOREIGN KEY (IdInsumoProducido) REFERENCES dbo.Insumo (Id);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = 'CK_Receta_Elaboracion' AND parent_object_id = OBJECT_ID('dbo.Receta')
)
BEGIN
    ALTER TABLE dbo.Receta
        ADD CONSTRAINT CK_Receta_Elaboracion CHECK (
            (IdInsumoProducido IS NULL AND Rinde IS NULL AND DiasVencimiento IS NULL)
            OR (IdInsumoProducido IS NOT NULL AND Rinde > 0 AND (DiasVencimiento IS NULL OR DiasVencimiento > 0))
        );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE name = 'UX_Receta_InsumoProducido' AND object_id = OBJECT_ID('dbo.Receta')
)
BEGIN
    CREATE UNIQUE INDEX UX_Receta_InsumoProducido ON dbo.Receta (IdInsumoProducido) WHERE IdInsumoProducido IS NOT NULL;
END
GO

-- ---------- Produccion ----------
IF OBJECT_ID('dbo.Produccion', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Produccion (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Produccion PRIMARY KEY,
        FechaHora DATETIME NOT NULL CONSTRAINT DF_Produccion_FechaHora DEFAULT GETDATE(),
        IdEmpleado INT NOT NULL CONSTRAINT FK_Produccion_Empleado FOREIGN KEY REFERENCES dbo.Empleado (Id),
        IdJornada INT NULL CONSTRAINT FK_Produccion_Jornada FOREIGN KEY REFERENCES dbo.Jornada (Id),
        IdReceta INT NOT NULL CONSTRAINT FK_Produccion_Receta FOREIGN KEY REFERENCES dbo.Receta (Id),
        IdInsumo INT NOT NULL CONSTRAINT FK_Produccion_Insumo FOREIGN KEY REFERENCES dbo.Insumo (Id),   -- el insumo que salio
        Tandas DECIMAL(12,3) NOT NULL,
        Cantidad DECIMAL(12,3) NOT NULL,      -- lo que salio, en la unidad base del insumo (Rinde x Tandas)
        Nota NVARCHAR(300) NULL,
        CONSTRAINT CK_Produccion_Tandas CHECK (Tandas > 0),
        CONSTRAINT CK_Produccion_Cantidad CHECK (Cantidad > 0)
    );
    CREATE INDEX IX_Produccion_FechaHora ON dbo.Produccion (FechaHora);
    CREATE INDEX IX_Produccion_Insumo ON dbo.Produccion (IdInsumo);
END
GO

-- ---------- MovimientoStock.IdProduccion ----------
IF COL_LENGTH('dbo.MovimientoStock', 'IdProduccion') IS NULL
BEGIN
    ALTER TABLE dbo.MovimientoStock ADD IdProduccion INT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_MovimientoStock_Produccion' AND parent_object_id = OBJECT_ID('dbo.MovimientoStock')
)
BEGIN
    ALTER TABLE dbo.MovimientoStock
        ADD CONSTRAINT FK_MovimientoStock_Produccion FOREIGN KEY (IdProduccion) REFERENCES dbo.Produccion (Id);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE name = 'IX_MovimientoStock_Produccion' AND object_id = OBJECT_ID('dbo.MovimientoStock')
)
BEGIN
    CREATE INDEX IX_MovimientoStock_Produccion ON dbo.MovimientoStock (IdProduccion) WHERE IdProduccion IS NOT NULL;
END
GO

-- ---------- Configuracion ----------
IF OBJECT_ID('dbo.Configuracion', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Configuracion (
        Clave NVARCHAR(50) NOT NULL CONSTRAINT PK_Configuracion PRIMARY KEY,
        Valor NVARCHAR(200) NOT NULL,
        IdEmpleado INT NULL CONSTRAINT FK_Configuracion_Empleado FOREIGN KEY REFERENCES dbo.Empleado (Id),   -- quien la cambio por ultima vez
        ActualizadoEn DATETIME NOT NULL CONSTRAINT DF_Configuracion_ActualizadoEn DEFAULT GETDATE()
    );
END
GO

-- Dias de anticipacion con que se avisa que un lote esta por vencer (5 por defecto; Admin y Gerente lo cambian)
IF NOT EXISTS (SELECT 1 FROM dbo.Configuracion WHERE Clave = N'dias_aviso_vencimiento')
BEGIN
    INSERT INTO dbo.Configuracion (Clave, Valor) VALUES (N'dias_aviso_vencimiento', N'5');
END
GO
