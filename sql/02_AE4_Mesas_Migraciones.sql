USE RestauranteDB;
GO

-- Baja logica de mesas: columna Activa (1 = en uso, 0 = dada de baja)
IF COL_LENGTH('dbo.Mesa', 'Activa') IS NULL
BEGIN
    ALTER TABLE dbo.Mesa
    ADD Activa BIT NOT NULL CONSTRAINT DF_Mesa_Activa DEFAULT (1);
END
GO

-- El Numero de mesa es el identificador visible: no puede repetirse
IF NOT EXISTS (
    SELECT 1 FROM sys.key_constraints
    WHERE name = 'UQ_Mesa_Numero'
      AND parent_object_id = OBJECT_ID('dbo.Mesa')
)
BEGIN
    IF EXISTS (SELECT Numero FROM dbo.Mesa GROUP BY Numero HAVING COUNT(*) > 1)
        RAISERROR('Hay mesas con Numero repetido: corregirlas antes de crear UQ_Mesa_Numero.', 16, 1);
    ELSE
        ALTER TABLE dbo.Mesa ADD CONSTRAINT UQ_Mesa_Numero UNIQUE (Numero);
END
GO
