USE RestauranteDB;
GO

-- Disponibilidad de los productos (separada de la carta).
--   Producto.Activo         : decision de CARTA. Solo la cambia una persona (Admin/Gerente: "Ocultar plato").
--   Producto.Disponible     : lo calcula el STOCK (hito 3): 0 si faltan insumos para prepararlo. Se reactiva solo al reponer.
--   Producto.AgotadoManual  : override de COCINA ("sin insumos"). NO se reactiva solo al reponer: alguien tiene que
--                             reactivarlo, y no se puede mientras el stock no alcance. Al reponer, el sistema solo avisa.
--   FechaHoraAgotado / IdEmpleadoAgotado : cuando y quien lo marco (para la alerta "se puede volver a reactivar").
-- El cliente ve un producto solo si Activo = 1 AND Disponible = 1 AND AgotadoManual = 0.
-- Es idempotente: se puede ejecutar mas de una vez. Los productos existentes quedan disponibles.

IF COL_LENGTH('dbo.Producto', 'Disponible') IS NULL
    ALTER TABLE dbo.Producto ADD Disponible BIT NOT NULL CONSTRAINT DF_Producto_Disponible DEFAULT 1;
GO

IF COL_LENGTH('dbo.Producto', 'AgotadoManual') IS NULL
    ALTER TABLE dbo.Producto ADD AgotadoManual BIT NOT NULL CONSTRAINT DF_Producto_AgotadoManual DEFAULT 0;
GO

IF COL_LENGTH('dbo.Producto', 'FechaHoraAgotado') IS NULL
    ALTER TABLE dbo.Producto ADD FechaHoraAgotado DATETIME NULL;
GO

IF COL_LENGTH('dbo.Producto', 'IdEmpleadoAgotado') IS NULL
    ALTER TABLE dbo.Producto ADD IdEmpleadoAgotado INT NULL;
GO

-- La FK va en otro lote: la columna tiene que existir antes de referenciarla
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Producto_EmpleadoAgotado')
    ALTER TABLE dbo.Producto
        ADD CONSTRAINT FK_Producto_EmpleadoAgotado FOREIGN KEY (IdEmpleadoAgotado) REFERENCES dbo.Empleado (Id);
GO
