USE RestauranteDB;
GO

-- Jornada (Hito 0) y turnos de atencion.
--   Turno   : horario de atencion del local (almuerzo, cena...). Lo edita solo el Gerente desde la API.
--   Jornada : periodo en que el local esta abierto al publico. Una sola abierta a la vez; el boton
--             "Comenzar jornada" (Admin y Gerente) la abre y el de cierre la cierra. Puede haber varias por dia.
--   PedidoCabecera.IdJornada : jornada en la que se abrio la mesa (la venta pertenece a esa jornada,
--             aunque se cobre despues de cerrarla o pasada la medianoche).
-- Es idempotente: se puede ejecutar mas de una vez.

-- ---------- Turno ----------
IF OBJECT_ID('dbo.Turno', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Turno (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Turno PRIMARY KEY,
        Nombre NVARCHAR(30) NOT NULL,
        HoraApertura TIME(0) NOT NULL,
        HoraCierre TIME(0) NOT NULL,   -- si es menor o igual a la apertura, el turno termina al dia siguiente
        Activo BIT NOT NULL CONSTRAINT DF_Turno_Activo DEFAULT 1,
        CONSTRAINT UQ_Turno_Nombre UNIQUE (Nombre),
        CONSTRAINT CK_Turno_Horas CHECK (HoraApertura <> HoraCierre)
    );
END
GO

-- Horarios iniciales (el Gerente los puede cambiar desde la API)
IF NOT EXISTS (SELECT 1 FROM dbo.Turno WHERE Nombre = N'Almuerzo')
    INSERT INTO dbo.Turno (Nombre, HoraApertura, HoraCierre) VALUES (N'Almuerzo', '10:00', '15:00');
IF NOT EXISTS (SELECT 1 FROM dbo.Turno WHERE Nombre = N'Cena')
    INSERT INTO dbo.Turno (Nombre, HoraApertura, HoraCierre) VALUES (N'Cena', '20:00', '00:30');
GO

-- ---------- Jornada ----------
IF OBJECT_ID('dbo.Jornada', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Jornada (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Jornada PRIMARY KEY,
        IdTurno INT NOT NULL CONSTRAINT FK_Jornada_Turno FOREIGN KEY REFERENCES dbo.Turno (Id),
        Fecha DATE NOT NULL,                       -- fecha local en que se abrio (a esa fecha pertenece, aunque cierre pasada la medianoche)
        FechaHoraApertura DATETIME NOT NULL,
        IdEmpleadoApertura INT NOT NULL CONSTRAINT FK_Jornada_EmpleadoApertura FOREIGN KEY REFERENCES dbo.Empleado (Id),
        FechaHoraCierre DATETIME NULL,
        IdEmpleadoCierre INT NULL CONSTRAINT FK_Jornada_EmpleadoCierre FOREIGN KEY REFERENCES dbo.Empleado (Id),
        Estado NVARCHAR(10) NOT NULL CONSTRAINT DF_Jornada_Estado DEFAULT N'Abierta',
        CONSTRAINT CK_Jornada_Estado CHECK (Estado IN (N'Abierta', N'Cerrada'))
    );
END
GO

-- Solo puede haber una jornada abierta a la vez (lo garantiza la base, no solo la API)
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UQ_Jornada_Abierta' AND object_id = OBJECT_ID('dbo.Jornada')
)
    CREATE UNIQUE INDEX UQ_Jornada_Abierta ON dbo.Jornada (Estado) WHERE Estado = N'Abierta';
GO

-- ---------- PedidoCabecera.IdJornada ----------
-- NULL en las sesiones anteriores a este script (no se les inventa una jornada)
IF COL_LENGTH('dbo.PedidoCabecera', 'IdJornada') IS NULL
    ALTER TABLE dbo.PedidoCabecera ADD IdJornada INT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_PedidoCabecera_Jornada')
    ALTER TABLE dbo.PedidoCabecera
        ADD CONSTRAINT FK_PedidoCabecera_Jornada FOREIGN KEY (IdJornada) REFERENCES dbo.Jornada (Id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_PedidoCabecera_IdJornada' AND object_id = OBJECT_ID('dbo.PedidoCabecera')
)
    CREATE INDEX IX_PedidoCabecera_IdJornada ON dbo.PedidoCabecera (IdJornada);
GO
