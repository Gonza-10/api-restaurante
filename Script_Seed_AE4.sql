-- =========================================================
-- Savage Grill - Datos semilla (AE4)
-- Idempotente: cada fila se inserta solo si no existe
-- (roles/categorias/productos por Nombre, mesas por Numero,
-- empleados por Usuario). Se puede ejecutar mas de una vez
-- y no modifica filas ya cargadas (salvo la clave de los 5 usuarios de demo).
-- Requisito: haber ejecutado Script_Creacion_RestauranteDB.sql
-- (o Script_AE4_Mesas_Migraciones.sql en una base existente).
-- No carga sesiones de mesa: las abre el mozo desde la API.
-- Las marcas de vegetariano / sin TACC son de ejemplo: revisar.
-- =========================================================
USE RestauranteDB;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;

-- Roles
INSERT INTO Rol (Nombre)
SELECT v.Nombre
FROM (VALUES (N'Mozo'), (N'Cocina'), (N'Admin'), (N'Gerente')) AS v(Nombre)
WHERE NOT EXISTS (SELECT 1 FROM Rol r WHERE r.Nombre = v.Nombre);

-- Empleados de demostracion. Contrasena de TODOS: 1234 (solo para desarrollo).
-- Se guarda hasheada con PBKDF2, igual que hace la API. Cambiar antes de usar login real.
DECLARE @HashDemo NVARCHAR(256) = N'pbkdf2_sha256$1500000$enNrHqd1u3h4ZgouX9jZXL$tof/Z69B6/9aExFNMRrOFtDQsGZIvbed2P6dvBZ6Dew=';

INSERT INTO Empleado (Nombre, Apellido, IdRol, Usuario, [ContraseñaHash], Activo, FechaIngreso)
SELECT v.Nombre, v.Apellido, r.Id, v.Usuario, @HashDemo, 1, GETDATE()
FROM (VALUES
    (N'Juan', N'Perez', N'Mozo', N'jperez'),
    (N'Marcos', N'Vera', N'Mozo', N'mvera'),
    (N'Carla', N'Ruiz', N'Cocina', N'cruiz'),
    (N'Ana', N'Gomez', N'Admin', N'agomez'),
    (N'Luis', N'Martinez', N'Gerente', N'lmartinez')
) AS v(Nombre, Apellido, Rol, Usuario)
JOIN Rol r ON r.Nombre = v.Rol
WHERE NOT EXISTS (SELECT 1 FROM Empleado e WHERE e.Usuario = v.Usuario);

-- Si estos usuarios ya existian (seed anterior), se les unifica la clave de demostracion
UPDATE Empleado SET [ContraseñaHash] = @HashDemo
WHERE Usuario IN (N'jperez', N'mvera', N'cruiz', N'agomez', N'lmartinez');

-- Mesas (Numero, CapacidadMaxima)
INSERT INTO Mesa (Numero, CapacidadMaxima, Estado, Activa)
SELECT v.Numero, v.Capacidad, 0, 1
FROM (VALUES (1, 2), (2, 4), (3, 4), (4, 2), (5, 4), (6, 4), (7, 6), (8, 6), (9, 8)) AS v(Numero, Capacidad)
WHERE NOT EXISTS (SELECT 1 FROM Mesa m WHERE m.Numero = v.Numero);

-- Categorias
INSERT INTO Categoria (Nombre)
SELECT v.Nombre
FROM (VALUES (N'Bebidas'), (N'Principales'), (N'Entradas'), (N'Postres'), (N'Tragos')) AS v(Nombre)
WHERE NOT EXISTS (SELECT 1 FROM Categoria c WHERE c.Nombre = v.Nombre);

-- Productos (Nombre, Precio, Categoria, EsVegetariano, AptoCeliaco)
INSERT INTO Producto (Nombre, PrecioActual, IdCategoria, EsVegetariano, AptoCeliaco, Activo)
SELECT v.Nombre, v.Precio, c.Id, v.Veg, v.Cel, 1
FROM (VALUES
    (N'Coca-Cola 1L', 3800.00, N'Bebidas', 0, 0),
    (N'Savage Burger Doble', 14500.00, N'Principales', 0, 0),
    (N'Milanesa Napolitana', 12000.00, N'Principales', 0, 0),
    (N'Ensalada César', 8500.00, N'Principales', 1, 1),
    (N'Pizza Muzzarella', 11000.00, N'Principales', 1, 0),
    (N'Provoleta a la Parrilla', 7500.00, N'Entradas', 1, 1),
    (N'Empanadas de Carne x3', 6900.00, N'Entradas', 0, 0),
    (N'Papas Savage con Cheddar y Panceta', 7200.00, N'Entradas', 0, 0),
    (N'Bastones de Muzzarella', 7800.00, N'Entradas', 1, 0),
    (N'Tabla de Picada para 3', 18500.00, N'Entradas', 0, 0),
    (N'Burger Clásica', 11500.00, N'Principales', 0, 0),
    (N'Burger Veggie', 11000.00, N'Principales', 1, 0),
    (N'Milanesa con Papas Fritas', 11500.00, N'Principales', 0, 0),
    (N'Galeto al Limón', 13500.00, N'Principales', 0, 0),
    (N'Bife de Chorizo con Papas', 17800.00, N'Principales', 0, 1),
    (N'Pasta Ravioles de Ricota', 12500.00, N'Principales', 1, 0),
    (N'Pasta al Wok con Queso Sardo', 11800.00, N'Principales', 1, 0),
    (N'Ensalada Caprese', 8200.00, N'Principales', 1, 1),
    (N'Pizza Napolitana', 12000.00, N'Principales', 1, 0),
    (N'Pizza Fugazzeta', 12500.00, N'Principales', 1, 0),
    (N'Flan Casero con Dulce de Leche', 5500.00, N'Postres', 1, 1),
    (N'Brownie con Helado', 6900.00, N'Postres', 1, 0),
    (N'Panqueque de Dulce de Leche', 5900.00, N'Postres', 1, 0),
    (N'Helado 3 Bochas', 5200.00, N'Postres', 1, 1),
    (N'Agua Mineral 500 ml', 1800.00, N'Bebidas', 1, 1),
    (N'Gaseosa Línea Coca-Cola 500 ml', 2500.00, N'Bebidas', 0, 0),
    (N'Jugo de Naranja Natural', 3800.00, N'Bebidas', 1, 1),
    (N'Limonada con Menta y Jengibre', 3800.00, N'Bebidas', 1, 1),
    (N'Cerveza Rubia Pinta', 4500.00, N'Bebidas', 1, 0),
    (N'Cerveza IPA Artesanal Pinta', 4800.00, N'Bebidas', 1, 0),
    (N'Fernet con Coca', 5500.00, N'Tragos', 1, 1),
    (N'Gin Tonic', 6800.00, N'Tragos', 1, 1),
    (N'Negroni', 7500.00, N'Tragos', 1, 1),
    (N'Mojito', 7200.00, N'Tragos', 1, 1),
    (N'Aperol Spritz', 7200.00, N'Tragos', 1, 1)
) AS v(Nombre, Precio, Categoria, Veg, Cel)
JOIN Categoria c ON c.Nombre = v.Categoria
WHERE NOT EXISTS (SELECT 1 FROM Producto p WHERE p.Nombre = v.Nombre);

COMMIT TRANSACTION;

-- Resumen
SELECT 'Rol' AS Tabla, COUNT(*) AS Filas FROM Rol
UNION ALL SELECT 'Empleado', COUNT(*) FROM Empleado
UNION ALL SELECT 'Mesa', COUNT(*) FROM Mesa
UNION ALL SELECT 'Categoria', COUNT(*) FROM Categoria
UNION ALL SELECT 'Producto', COUNT(*) FROM Producto;
GO
