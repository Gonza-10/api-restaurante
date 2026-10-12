USE RestauranteDB;
GO

-- Descripcion e imagen de cada producto. ImagenUrl guarda un link https:// externo
-- o la ruta de una foto subida al servidor (/media/productos/<id>.jpg|png|webp)
IF COL_LENGTH('dbo.Producto', 'Descripcion') IS NULL
    ALTER TABLE dbo.Producto ADD Descripcion NVARCHAR(500) NULL;
GO

IF COL_LENGTH('dbo.Producto', 'ImagenUrl') IS NULL
    ALTER TABLE dbo.Producto ADD ImagenUrl NVARCHAR(500) NULL;
GO
