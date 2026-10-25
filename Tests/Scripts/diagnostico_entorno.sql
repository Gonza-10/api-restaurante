-- =====================================================================================
-- Diagnostico del entorno (SOLO LECTURA: no modifica nada).
-- Ejecutar en SSMS conectado a la base RestauranteDB (o a la que se este usando).
-- Dice que scripts faltan correr y si hay datos base (turnos, mesas, roles, empleados, productos).
-- Columna Estado: OK / FALTA. Si algo dice FALTA, correr el script indicado en Detalle (ver README).
-- =====================================================================================
SET NOCOUNT ON;

DECLARE @r TABLE (Orden INT IDENTITY(1,1), Chequeo NVARCHAR(60), Estado NVARCHAR(6), Detalle NVARCHAR(200));

-- ---------- tablas ----------
INSERT @r (Chequeo, Estado, Detalle)
SELECT t.Nombre, IIF(OBJECT_ID('dbo.' + t.Nombre, 'U') IS NULL, 'FALTA', 'OK'), t.Script
FROM (VALUES
    (N'Rol',              N'Script_Creacion_RestauranteDB.sql'),
    (N'Empleado',         N'Script_Creacion_RestauranteDB.sql'),
    (N'Mesa',             N'Script_Creacion_RestauranteDB.sql'),
    (N'Producto',         N'Script_Creacion_RestauranteDB.sql'),
    (N'PedidoCabecera',   N'Script_Creacion_RestauranteDB.sql'),
    (N'ComandaRecibida',  N'Script_AE2_Migraciones.sql'),
    (N'Turno',            N'Script_AE4_Jornada_Migraciones.sql'),
    (N'Jornada',          N'Script_AE4_Jornada_Migraciones.sql'),
    (N'Especial',         N'Script_AE4_Especiales_Migraciones.sql'),
    (N'DiaEspecial',      N'Script_AE4_Especiales_Migraciones.sql')
) AS t (Nombre, Script);

-- ---------- columnas que agregan las migraciones ----------
INSERT @r (Chequeo, Estado, Detalle)
SELECT c.Tabla + N'.' + c.Columna, IIF(COL_LENGTH('dbo.' + c.Tabla, c.Columna) IS NULL, 'FALTA', 'OK'), c.Script
FROM (VALUES
    (N'Mesa',           N'Activa',                 N'Script_AE4_Mesas_Migraciones.sql'),
    (N'Producto',       N'Descripcion',            N'Script_AE4_Productos_Migraciones.sql'),
    (N'Producto',       N'TiempoEstimadoMin',      N'Script_AE4_Tiempos_Migraciones.sql'),
    (N'PedidoCabecera', N'FechaHoraSolicitaCuenta',N'Script_AE4_Cuenta_Migraciones.sql'),
    (N'PedidoCabecera', N'IdJornada',              N'Script_AE4_Jornada_Migraciones.sql'),
    (N'Producto',       N'Disponible',             N'Script_AE4_Disponibilidad_Migraciones.sql'),
    (N'Producto',       N'AgotadoManual',          N'Script_AE4_Disponibilidad_Migraciones.sql')
) AS c (Tabla, Columna, Script)
WHERE OBJECT_ID('dbo.' + c.Tabla, 'U') IS NOT NULL;

-- ---------- datos base (solo si la tabla existe) ----------
DECLARE @n INT;

IF OBJECT_ID('dbo.Turno', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Turno WHERE Activo = 1', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: turnos activos', IIF(@n >= 1, 'OK', 'FALTA'), CONCAT(@n, N' (los carga Script_AE4_Jornada_Migraciones.sql)'));
END;

IF OBJECT_ID('dbo.Mesa', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Mesa', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: mesas', IIF(@n >= 1, 'OK', 'FALTA'), CONCAT(@n, N' (las carga Script_Seed_AE4.sql)'));
END;

IF OBJECT_ID('dbo.Rol', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Rol', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: roles', IIF(@n >= 4, 'OK', 'FALTA'), CONCAT(@n, N' (4 esperados; los carga Script_Seed_AE4.sql)'));
END;

IF OBJECT_ID('dbo.Empleado', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Empleado', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: empleados', IIF(@n >= 1, 'OK', 'FALTA'), CONCAT(@n, N' (los carga Script_Seed_AE4.sql)'));
END;

IF OBJECT_ID('dbo.Producto', 'U') IS NOT NULL
BEGIN
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.Producto', N'@n INT OUTPUT', @n OUTPUT;
    INSERT @r VALUES (N'Datos: productos', IIF(@n >= 1, 'OK', 'FALTA'), CONCAT(@n, N' (los carga Script_Seed_AE4.sql)'));
END;

SELECT Chequeo, Estado, Detalle FROM @r ORDER BY Orden;

-- ---------- informativo: turnos y jornada abierta ----------
IF OBJECT_ID('dbo.Turno', 'U') IS NOT NULL
    SELECT Id, Nombre, HoraApertura, HoraCierre, Activo FROM dbo.Turno ORDER BY Id;

IF OBJECT_ID('dbo.Jornada', 'U') IS NOT NULL
    SELECT Id, IdTurno, Fecha, Estado, FechaHoraApertura FROM dbo.Jornada WHERE Estado = 'Abierta';
