USE RestauranteDB;
GO

-- Cobros, hito 5: extras por receta ("agregale mas cheddar", "aderezo extra").
--
-- RecetaExtra -> un extra que se puede sumar a un plato, ligado a la RECETA (todos los platos que usan esa receta lo ofrecen).
--            IdInsumo  : el insumo que gasta el extra. Puede ser un insumo que la receta ya usa (mas cheddar) o uno nuevo (aderezo).
--            Cantidad  : cuanto gasta UNA unidad de extra, en la unidad base del insumo (g, ml o u). Se suma a la receta del plato.
--            Precio    : recargo por UNA unidad de extra, en pesos. Se suma al precio del plato.
--            MaxPorUnidad : cuantas unidades del extra admite cada unidad de plato (1 = se puede agregar o no).
--            Activo    : lo decide Admin/Gerente. Un extra no se borra (queda en el historial de los pedidos): se desactiva.
--            Disponible: lo calcula el stock (hay para UNA unidad de extra). Un extra no disponible no se ofrece al cliente.
-- PedidoDetalleExtra -> los extras de cada renglon del pedido, con el recargo CONGELADO al momento de pedir.
--            Cantidad : unidades de extra por cada unidad del plato. PrecioUnitario: recargo por unidad de extra.
--            PedidoDetalle.PrecioUnitario ya incluye los extras (precio del plato + recargos).
--
-- Requiere el 12 (recetas) y el 14 (modificadores). Es idempotente: se puede ejecutar mas de una vez.

IF OBJECT_ID('dbo.RecetaExtra', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RecetaExtra (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RecetaExtra PRIMARY KEY,
        IdReceta INT NOT NULL
            CONSTRAINT FK_RecetaExtra_Receta FOREIGN KEY REFERENCES dbo.Receta (Id) ON DELETE CASCADE,
        IdInsumo INT NOT NULL
            CONSTRAINT FK_RecetaExtra_Insumo FOREIGN KEY REFERENCES dbo.Insumo (Id),
        Cantidad DECIMAL(12,3) NOT NULL CONSTRAINT CK_RecetaExtra_Cantidad CHECK (Cantidad > 0),
        Precio DECIMAL(10,2) NOT NULL CONSTRAINT CK_RecetaExtra_Precio CHECK (Precio >= 0),
        MaxPorUnidad INT NOT NULL CONSTRAINT DF_RecetaExtra_Max DEFAULT 1
            CONSTRAINT CK_RecetaExtra_Max CHECK (MaxPorUnidad BETWEEN 1 AND 10),
        Activo BIT NOT NULL CONSTRAINT DF_RecetaExtra_Activo DEFAULT 1,
        Disponible BIT NOT NULL CONSTRAINT DF_RecetaExtra_Disponible DEFAULT 1,
        CONSTRAINT UQ_RecetaExtra UNIQUE (IdReceta, IdInsumo)   -- un insumo se ofrece una sola vez como extra de una receta
    );
    CREATE INDEX IX_RecetaExtra_Insumo ON dbo.RecetaExtra (IdInsumo);
END
GO

IF OBJECT_ID('dbo.PedidoDetalleExtra', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PedidoDetalleExtra (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_PedidoDetalleExtra PRIMARY KEY,
        IdPedidoDetalle INT NOT NULL
            CONSTRAINT FK_PedidoDetalleExtra_Detalle FOREIGN KEY REFERENCES dbo.PedidoDetalle (Id) ON DELETE CASCADE,
        IdRecetaExtra INT NOT NULL
            CONSTRAINT FK_PedidoDetalleExtra_Extra FOREIGN KEY REFERENCES dbo.RecetaExtra (Id),
        IdInsumo INT NOT NULL
            CONSTRAINT FK_PedidoDetalleExtra_Insumo FOREIGN KEY REFERENCES dbo.Insumo (Id),
        Cantidad INT NOT NULL CONSTRAINT CK_PedidoDetalleExtra_Cantidad CHECK (Cantidad >= 1),
        PrecioUnitario DECIMAL(10,2) NOT NULL CONSTRAINT CK_PedidoDetalleExtra_Precio CHECK (PrecioUnitario >= 0),
        CONSTRAINT UQ_PedidoDetalleExtra UNIQUE (IdPedidoDetalle, IdRecetaExtra)   -- un extra por renglon (con su cantidad)
    );
    CREATE INDEX IX_PedidoDetalleExtra_Extra ON dbo.PedidoDetalleExtra (IdRecetaExtra);
END
GO
PRINT 'Script 21 (extras) aplicado.';
GO
