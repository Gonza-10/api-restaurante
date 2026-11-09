USE RestauranteDB;
GO

-- Reservas: la gestionan Admin y Gerente (llamadas y mensajes). Una reserva bloquea la mesa durante TODA la jornada
-- (fecha + turno: Almuerzo, Cena...). No tiene duracion: la mesa se libera cuando el cliente llega (Cumplida), cuando se
-- cancela (Cancelada) o cuando pasa la tolerancia de llegada sin que aparezca (No se presentó, lo marca el sistema).
--
-- Reserva (ya existia desde el script 00, sin vistas ni uso) recibe:
--   IdTurno              turno de la reserva (FK a Turno). Junto con Fecha forma la "jornada" reservada.
--   CantidadPersonas     para validar la capacidad de la mesa.
--   Notas, Origen        pedidos especiales / como se pidio (Llamada, Mensaje, Otro). Opcionales.
--   FechaHoraAlta        cuando se cargo.
--   FechaHoraCancelacion, IdEmpleadoCancelacion, MotivoCancelacion   quien la cancelo, cuando y por que.
--   FechaHoraResolucion  cuando paso a Cumplida o a No se presentó.
--   IdPedidoCabecera     la sesion de mesa que la cumplio.
-- Estados validos: Confirmada, Cancelada, Cumplida, No se presentó.
-- Indice unico filtrado: una sola reserva Confirmada por mesa, fecha y turno (la base lo garantiza aunque dos personas
-- reserven al mismo tiempo).
--
-- Requiere el 00 (Reserva, Mesa, Empleado, PedidoCabecera) y el 08 (Turno). Es idempotente: se puede ejecutar mas de una vez.

IF COL_LENGTH('dbo.Reserva', 'IdTurno') IS NULL
    ALTER TABLE dbo.Reserva ADD IdTurno INT NULL;
GO

-- Reservas viejas (si las hubiera): se les asigna el turno cuyo horario incluye su hora, o el primero.
UPDATE r
SET IdTurno = COALESCE(
    (SELECT TOP 1 t.Id FROM dbo.Turno t
     WHERE (t.HoraApertura < t.HoraCierre AND r.Hora >= t.HoraApertura AND r.Hora < t.HoraCierre)
        OR (t.HoraApertura >= t.HoraCierre AND (r.Hora >= t.HoraApertura OR r.Hora < t.HoraCierre))
     ORDER BY t.HoraApertura),
    (SELECT TOP 1 Id FROM dbo.Turno ORDER BY HoraApertura))
FROM dbo.Reserva r
WHERE r.IdTurno IS NULL;
GO

IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.Reserva') AND name = 'IdTurno' AND is_nullable = 1)
    ALTER TABLE dbo.Reserva ALTER COLUMN IdTurno INT NOT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Reserva_Turno')
    ALTER TABLE dbo.Reserva ADD CONSTRAINT FK_Reserva_Turno FOREIGN KEY (IdTurno) REFERENCES dbo.Turno(Id);
GO

IF COL_LENGTH('dbo.Reserva', 'CantidadPersonas') IS NULL
    ALTER TABLE dbo.Reserva ADD CantidadPersonas INT NOT NULL CONSTRAINT DF_Reserva_CantidadPersonas DEFAULT 1;
GO

IF COL_LENGTH('dbo.Reserva', 'Notas') IS NULL
    ALTER TABLE dbo.Reserva ADD Notas NVARCHAR(300) NULL;
GO

IF COL_LENGTH('dbo.Reserva', 'Origen') IS NULL
    ALTER TABLE dbo.Reserva ADD Origen NVARCHAR(20) NULL;
GO

IF COL_LENGTH('dbo.Reserva', 'FechaHoraAlta') IS NULL
    ALTER TABLE dbo.Reserva ADD FechaHoraAlta DATETIME NOT NULL CONSTRAINT DF_Reserva_FechaHoraAlta DEFAULT GETDATE();
GO

IF COL_LENGTH('dbo.Reserva', 'FechaHoraCancelacion') IS NULL
    ALTER TABLE dbo.Reserva ADD FechaHoraCancelacion DATETIME NULL;
GO

IF COL_LENGTH('dbo.Reserva', 'IdEmpleadoCancelacion') IS NULL
    ALTER TABLE dbo.Reserva ADD IdEmpleadoCancelacion INT NULL;
GO

IF COL_LENGTH('dbo.Reserva', 'MotivoCancelacion') IS NULL
    ALTER TABLE dbo.Reserva ADD MotivoCancelacion NVARCHAR(200) NULL;
GO

IF COL_LENGTH('dbo.Reserva', 'FechaHoraResolucion') IS NULL
    ALTER TABLE dbo.Reserva ADD FechaHoraResolucion DATETIME NULL;
GO

IF COL_LENGTH('dbo.Reserva', 'IdPedidoCabecera') IS NULL
    ALTER TABLE dbo.Reserva ADD IdPedidoCabecera INT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Reserva_EmpleadoCancelacion')
    ALTER TABLE dbo.Reserva ADD CONSTRAINT FK_Reserva_EmpleadoCancelacion FOREIGN KEY (IdEmpleadoCancelacion) REFERENCES dbo.Empleado(Id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Reserva_PedidoCabecera')
    ALTER TABLE dbo.Reserva ADD CONSTRAINT FK_Reserva_PedidoCabecera FOREIGN KEY (IdPedidoCabecera) REFERENCES dbo.PedidoCabecera(Id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Reserva_Estado')
    ALTER TABLE dbo.Reserva ADD CONSTRAINT CK_Reserva_Estado
        CHECK (Estado IN (N'Confirmada', N'Cancelada', N'Cumplida', N'No se presentó'));
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Reserva_CantidadPersonas')
    ALTER TABLE dbo.Reserva ADD CONSTRAINT CK_Reserva_CantidadPersonas CHECK (CantidadPersonas >= 1);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_Reserva_Mesa_Jornada_Confirmada' AND object_id = OBJECT_ID('dbo.Reserva'))
    CREATE UNIQUE INDEX UQ_Reserva_Mesa_Jornada_Confirmada ON dbo.Reserva (IdMesa, Fecha, IdTurno)
        WHERE Estado = N'Confirmada' AND IdMesa IS NOT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Reserva_Fecha_Turno' AND object_id = OBJECT_ID('dbo.Reserva'))
    CREATE INDEX IX_Reserva_Fecha_Turno ON dbo.Reserva (Fecha, IdTurno) INCLUDE (IdMesa, Estado);
GO
PRINT 'Script 23 (reservas) aplicado.';
GO
