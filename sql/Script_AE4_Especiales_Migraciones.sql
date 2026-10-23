USE RestauranteDB;
GO

-- Bug #8: especiales (promos) por dia, con calendario.
--   Especial    : un plato con precio especial. Es una regla SEMANAL (DiaSemana 1=lunes ... 7=domingo)
--                 o una excepcion para una FECHA puntual (exactamente una de las dos). El turno (IdTurno)
--                 limita a almuerzo o cena; NULL = todo el dia.
--   DiaEspecial : configuracion de una fecha puntual. Reemplaza = 1: ese dia valen SOLO los especiales de la fecha
--                 (con 0 se SUMAN a los de la regla semanal). Una fecha sin filas y con Reemplaza = 1 es un dia sin especiales.
-- Requiere haber ejecutado antes Script_AE4_Jornada_Migraciones.sql (usa la tabla Turno).
-- Es idempotente: se puede ejecutar mas de una vez.

IF OBJECT_ID('dbo.Turno', 'U') IS NULL
    RAISERROR('Falta la tabla Turno: ejecutar antes Script_AE4_Jornada_Migraciones.sql.', 16, 1);
GO

IF OBJECT_ID('dbo.DiaEspecial', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DiaEspecial (
        Fecha DATE NOT NULL CONSTRAINT PK_DiaEspecial PRIMARY KEY,
        Reemplaza BIT NOT NULL CONSTRAINT DF_DiaEspecial_Reemplaza DEFAULT 0,
        Nota NVARCHAR(100) NULL
    );
END
GO

IF OBJECT_ID('dbo.Especial', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Especial (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Especial PRIMARY KEY,
        IdProducto INT NOT NULL CONSTRAINT FK_Especial_Producto FOREIGN KEY REFERENCES dbo.Producto (Id) ON DELETE CASCADE,
        PrecioEspecial DECIMAL(10,2) NOT NULL CONSTRAINT CK_Especial_Precio CHECK (PrecioEspecial > 0),
        IdTurno INT NULL CONSTRAINT FK_Especial_Turno FOREIGN KEY REFERENCES dbo.Turno (Id),
        DiaSemana TINYINT NULL CONSTRAINT CK_Especial_DiaSemana CHECK (DiaSemana BETWEEN 1 AND 7),
        Fecha DATE NULL,
        CONSTRAINT CK_Especial_Regla CHECK (
            (DiaSemana IS NOT NULL AND Fecha IS NULL) OR (DiaSemana IS NULL AND Fecha IS NOT NULL)
        )
    );
END
GO

-- Un plato no se repite en la misma regla y turno (la API ademas rechaza turnos que se superponen)
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UQ_Especial_Regla' AND object_id = OBJECT_ID('dbo.Especial')
)
    CREATE UNIQUE INDEX UQ_Especial_Regla ON dbo.Especial (IdProducto, DiaSemana, Fecha, IdTurno);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_Especial_DiaSemana' AND object_id = OBJECT_ID('dbo.Especial')
)
    CREATE INDEX IX_Especial_DiaSemana ON dbo.Especial (DiaSemana);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_Especial_Fecha' AND object_id = OBJECT_ID('dbo.Especial')
)
    CREATE INDEX IX_Especial_Fecha ON dbo.Especial (Fecha);
GO
