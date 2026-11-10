USE RestauranteDB;
GO

-- Barra y destinos de los pedidos.
--
-- Cada producto se prepara o se entrega en un destino:
--   COCINA   lo ve el tablero de cocina (entradas, principales, postres...).
--   BARRA    lo prepara el bartender y lo ve el tablero de la barra (los tragos).
--   MOZO     no se prepara: lo lleva el mozo de la mesa, que recibe el aviso "Bebidas" y confirma la entrega.
--
-- Producto.Destino         destino propio del producto. NULL = el que le corresponde a su categoria (Tragos -> BARRA,
--                          Bebidas -> MOZO, el resto -> COCINA); la regla vive en el codigo (destinos_calculos.py), asi una
--                          categoria nueva no necesita tocar la base. Un valor cargado a mano gana sobre la categoria.
-- PedidoDetalle.Destino    destino del item en el momento de pedirse. Los items anteriores quedan en COCINA (asi se preparaban).
--                          No cambia si despues se edita el destino del producto.
-- Rol 'Bartender'          el rol de quien atiende la barra.
--
-- Una comanda con items de varios destinos se divide en Redis: una clave de estado por destino (ver estado_comandas.py).
-- Requiere el 00 (Rol), el 01 (Producto) y el 04 (PedidoDetalle). Es idempotente.

IF COL_LENGTH('dbo.Producto', 'Destino') IS NULL
    ALTER TABLE dbo.Producto ADD Destino NVARCHAR(10) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Producto_Destino')
    ALTER TABLE dbo.Producto ADD CONSTRAINT CK_Producto_Destino CHECK (Destino IS NULL OR Destino IN (N'COCINA', N'BARRA', N'MOZO'));
GO

IF COL_LENGTH('dbo.PedidoDetalle', 'Destino') IS NULL
    ALTER TABLE dbo.PedidoDetalle ADD Destino NVARCHAR(10) NOT NULL CONSTRAINT DF_PedidoDetalle_Destino DEFAULT N'COCINA';
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_PedidoDetalle_Destino')
    ALTER TABLE dbo.PedidoDetalle ADD CONSTRAINT CK_PedidoDetalle_Destino CHECK (Destino IN (N'COCINA', N'BARRA', N'MOZO'));
GO

IF NOT EXISTS (SELECT 1 FROM dbo.Rol WHERE Nombre = N'Bartender')
    INSERT INTO dbo.Rol (Nombre) VALUES (N'Bartender');
GO

PRINT 'Script 26 (barra y destinos de los pedidos) aplicado.';
GO
