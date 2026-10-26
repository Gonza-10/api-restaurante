USE RestauranteDB;
GO

-- Stock, hito 2: recetas y estado de la comanda.
--
-- Receta  -> entidad propia: que insumos y cuanto de cada uno gasta UNA unidad vendida. Se crea una sola vez y
--            los productos del menu la referencian (Producto.IdReceta). Asi no se duplican datos: varios
--            productos pueden usar la misma receta, y cada uno conserva su propio precio, descripcion y porciones.
-- RecetaIngrediente -> un renglon de la receta: insumo + cantidad en UNIDAD BASE (g, ml o u).
-- Producto.IdReceta -> NULL = el producto no lleva control de stock (por ejemplo una bebida que se vende cerrada).
--
-- ComandaRecibida.Estado -> 'Aceptada' o 'Rechazada'. Una comanda rechazada (falto stock cuando llego) queda
--            registrada igual, con el motivo interno (solo para el personal) y el mensaje que ve el cliente.
--            Asi, si RabbitMQ reentrega el mensaje, se reconoce y no se procesa de nuevo.
--
-- Fuera de este hito: sub-recetas y rinde (hito 6), modificadores de ingredientes (hito 5).
-- Es idempotente: se puede ejecutar mas de una vez.

-- ---------- Receta ----------
IF OBJECT_ID('dbo.Receta', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Receta (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Receta PRIMARY KEY,
        Nombre NVARCHAR(100) NOT NULL,
        Descripcion NVARCHAR(300) NULL,
        CONSTRAINT UQ_Receta_Nombre UNIQUE (Nombre)
    );
END
GO

-- ---------- RecetaIngrediente ----------
IF OBJECT_ID('dbo.RecetaIngrediente', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RecetaIngrediente (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RecetaIngrediente PRIMARY KEY,
        IdReceta INT NOT NULL
            CONSTRAINT FK_RecetaIngrediente_Receta FOREIGN KEY REFERENCES dbo.Receta (Id) ON DELETE CASCADE,
        IdInsumo INT NOT NULL
            CONSTRAINT FK_RecetaIngrediente_Insumo FOREIGN KEY REFERENCES dbo.Insumo (Id),
        Cantidad DECIMAL(12,3) NOT NULL,       -- en unidad base del insumo, por UNA unidad vendida
        CONSTRAINT CK_RecetaIngrediente_Cantidad CHECK (Cantidad > 0),
        CONSTRAINT UQ_RecetaIngrediente UNIQUE (IdReceta, IdInsumo)   -- un insumo aparece una sola vez por receta
    );
    CREATE INDEX IX_RecetaIngrediente_Insumo ON dbo.RecetaIngrediente (IdInsumo);
END
GO

-- ---------- Producto.IdReceta ----------
IF COL_LENGTH('dbo.Producto', 'IdReceta') IS NULL
BEGIN
    ALTER TABLE dbo.Producto ADD IdReceta INT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_Producto_Receta' AND parent_object_id = OBJECT_ID('dbo.Producto')
)
BEGIN
    ALTER TABLE dbo.Producto
        ADD CONSTRAINT FK_Producto_Receta FOREIGN KEY (IdReceta) REFERENCES dbo.Receta (Id);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes WHERE name = 'IX_Producto_Receta' AND object_id = OBJECT_ID('dbo.Producto')
)
BEGIN
    CREATE INDEX IX_Producto_Receta ON dbo.Producto (IdReceta);
END
GO

-- ---------- ComandaRecibida: estado, motivo y mensaje ----------
IF COL_LENGTH('dbo.ComandaRecibida', 'Estado') IS NULL
BEGIN
    -- las comandas que ya existian se procesaron bien: quedan 'Aceptada'
    ALTER TABLE dbo.ComandaRecibida
        ADD Estado NVARCHAR(10) NOT NULL CONSTRAINT DF_ComandaRecibida_Estado DEFAULT N'Aceptada';
END
GO

IF COL_LENGTH('dbo.ComandaRecibida', 'Motivo') IS NULL
BEGIN
    ALTER TABLE dbo.ComandaRecibida ADD Motivo NVARCHAR(500) NULL;           -- interno: que insumo falto (solo personal)
END
GO

IF COL_LENGTH('dbo.ComandaRecibida', 'MensajeCliente') IS NULL
BEGIN
    ALTER TABLE dbo.ComandaRecibida ADD MensajeCliente NVARCHAR(300) NULL;   -- lo que ve el cliente (generico)
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = 'CK_ComandaRecibida_Estado' AND parent_object_id = OBJECT_ID('dbo.ComandaRecibida')
)
BEGIN
    ALTER TABLE dbo.ComandaRecibida
        ADD CONSTRAINT CK_ComandaRecibida_Estado CHECK (Estado IN (N'Aceptada', N'Rechazada'));
END
GO
