USE RestauranteDB;
GO

-- Stock, hito 5: modificadores de los pedidos ("sin cebolla").
--
-- RecetaIngrediente.EsQuitable -> 1 si el cliente puede pedir el plato SIN ese ingrediente. Lo decide Admin/Gerente
--            al armar la receta. Un ingrediente fijo (0, el valor por defecto) no se puede quitar.
-- PedidoDetalleModificador -> lo que se quito en cada renglon del pedido: un registro por ingrediente quitado, enlazado
--            al renglon (PedidoDetalle) y al insumo. Es una lista (0, 1 o varios por renglon), por eso va en una
--            tabla hija y no en una columna. Lo que se quita no se descuenta del stock. Por ahora solo existe
--            el modificador "sin"; los extras (agregar con costo) se veran junto con el cobro.
--
-- Es idempotente: se puede ejecutar mas de una vez.

-- ---------- RecetaIngrediente.EsQuitable ----------
IF COL_LENGTH('dbo.RecetaIngrediente', 'EsQuitable') IS NULL
BEGIN
    ALTER TABLE dbo.RecetaIngrediente
        ADD EsQuitable BIT NOT NULL CONSTRAINT DF_RecetaIngrediente_EsQuitable DEFAULT 0;
END
GO

-- ---------- PedidoDetalleModificador ----------
IF OBJECT_ID('dbo.PedidoDetalleModificador', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PedidoDetalleModificador (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_PedidoDetalleModificador PRIMARY KEY,
        IdPedidoDetalle INT NOT NULL
            CONSTRAINT FK_PedidoDetalleModificador_Detalle FOREIGN KEY REFERENCES dbo.PedidoDetalle (Id) ON DELETE CASCADE,
        IdInsumo INT NOT NULL
            CONSTRAINT FK_PedidoDetalleModificador_Insumo FOREIGN KEY REFERENCES dbo.Insumo (Id),
        CONSTRAINT UQ_PedidoDetalleModificador UNIQUE (IdPedidoDetalle, IdInsumo)   -- un ingrediente se quita una sola vez por renglon
    );
    CREATE INDEX IX_PedidoDetalleModificador_Insumo ON dbo.PedidoDetalleModificador (IdInsumo);
END
GO
