USE RestauranteDB;
GO

-- Bug #5: tiempo estimado de preparacion (minutos) y porciones (personas que come) de cada producto.
-- Las columnas son opcionales (NULL = sin dato). Los valores iniciales de los productos del menu
-- los carga 99_Seed_AE4.sql (volver a ejecutarlo despues de este script: es idempotente
-- y solo completa los que estan vacios).
-- Es idempotente: se puede ejecutar mas de una vez.

IF COL_LENGTH('dbo.Producto', 'TiempoEstimadoMin') IS NULL
BEGIN
    ALTER TABLE Producto ADD TiempoEstimadoMin INT NULL;
END
GO

IF COL_LENGTH('dbo.Producto', 'Porciones') IS NULL
BEGIN
    ALTER TABLE Producto ADD Porciones INT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = 'CK_Producto_TiempoEstimado'
      AND parent_object_id = OBJECT_ID('dbo.Producto')
)
BEGIN
    ALTER TABLE Producto
        ADD CONSTRAINT CK_Producto_TiempoEstimado
        CHECK (TiempoEstimadoMin IS NULL OR TiempoEstimadoMin > 0);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = 'CK_Producto_Porciones'
      AND parent_object_id = OBJECT_ID('dbo.Producto')
)
BEGIN
    ALTER TABLE Producto
        ADD CONSTRAINT CK_Producto_Porciones
        CHECK (Porciones IS NULL OR Porciones > 0);
END
GO
