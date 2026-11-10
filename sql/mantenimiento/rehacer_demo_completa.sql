-- =====================================================================================================================
-- REHACER LA DEMO COMPLETA, DESDE CERO, EN UN SOLO SCRIPT.
--
-- NO es un script de la instalacion: no corre solo en el deploy. Se ejecuta a mano (SSMS).
--
-- !!! BORRA TODO LO OPERATIVO Y LA CARTA, y la rearma: no hay vuelta atras salvo restaurar una copia de seguridad. !!!
-- HACER ANTES LA COPIA DE SEGURIDAD (SSMS: clic derecho en RestauranteDB > Tasks > Back Up... > OK).
--
-- BORRA:   pedidos, comandas, comensales, facturas, pagos, cajas; TODOS los productos, recetas, insumos, lotes, compras,
--          proveedores, perdidas, producciones y especiales (incluida la basura de prueba ZZ). Las mesas quedan libres.
-- CONSERVA: empleados, roles, mesas, categorias, turnos, jornadas, cotizaciones, configuracion y reservas
--          (a las reservas se les suelta el vinculo con la sesion de mesa).
-- CREA:    los 35 productos de la carta (SIN fotos: se cargan despues con cargar_imagenes_productos), una receta por producto con
--          gramajes, ingredientes quitables y extras, 3 proveedores vinculados a los insumos y un stock realista con dos lotes
--          de vencimiento distinto en los perecederos.
--
-- @Aplicar viene en 1: ejecuta de verdad. Con @Aplicar = 0 hace todo, muestra el informe y lo DESHACE (ensayo).
-- Si algo falla en el medio, deshace TODO y lo informa. Despues: esperar 1 minuto (cache del menu) o reiniciar runserver.
-- =====================================================================================================================
USE RestauranteDB;
SET NOCOUNT ON;
SET XACT_ABORT OFF;

DECLARE @Aplicar BIT = 1;               -- 1 = aplicar de verdad | 0 = ensayo (no cambia nada)
DECLARE @BorrarReservas BIT = 0;        -- 1 = borra tambien todas las reservas
DECLARE @PorcionesFrescos INT = 40;     -- porciones que cubre el stock de perecederos
DECLARE @PorcionesAlmacen INT = 60;     -- porciones que cubre el stock de larga vida
DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);

DECLARE @Gerente INT = ISNULL(
    (SELECT Id FROM Empleado WHERE Usuario = N'lmartinez' AND Activo = 1),
    (SELECT TOP 1 e.Id FROM Empleado e JOIN Rol r ON r.Id = e.IdRol
     WHERE r.Nombre IN (N'Gerente', N'Admin') AND e.Activo = 1 ORDER BY e.Id));
IF @Gerente IS NULL
BEGIN
    PRINT N'No se encontro un empleado Gerente o Admin activo para registrar las compras. No se cambio nada.';
    RETURN;
END

-- ---------- datos de la carta ----------
DECLARE @Prod TABLE (Nombre NVARCHAR(80) PRIMARY KEY, Precio DECIMAL(10,2) NOT NULL, Categoria NVARCHAR(50) NOT NULL,
                     Veg BIT NOT NULL, Cel BIT NOT NULL, Descripcion NVARCHAR(500) NOT NULL);
INSERT INTO @Prod (Nombre, Precio, Categoria, Veg, Cel, Descripcion) VALUES
    (N'Coca-Cola 1L', 3800.00, N'Bebidas', 0, 0, N'Botella familiar de 1 litro, bien fr' + NCHAR(237) + N'a.'),
    (N'Savage Burger Doble', 14500.00, N'Principales', 0, 0, N'Dos medallones de carne, cheddar, panceta crocante, cebolla caramelizada y salsa de la casa en pan de papa.'),
    (N'Milanesa Napolitana', 12000.00, N'Principales', 0, 0, N'Milanesa de ternera con salsa de tomate, jam' + NCHAR(243) + N'n y muzzarella gratinada.'),
    (N'Ensalada C' + NCHAR(233) + N'sar', 8500.00, N'Principales', 1, 1, N'Lechuga, croutons, queso parmesano y aderezo C' + NCHAR(233) + N'sar.'),
    (N'Pizza Muzzarella', 11000.00, N'Principales', 1, 0, N'Pizza de masa casera con salsa de tomate, muzzarella y aceitunas.'),
    (N'Provoleta a la Parrilla', 7500.00, N'Entradas', 1, 1, N'Provolone grillado con or' + NCHAR(233) + N'gano y aceite de oliva.'),
    (N'Empanadas de Carne x3', 6900.00, N'Entradas', 0, 0, N'Tres empanadas de carne cortada a cuchillo, al horno.'),
    (N'Papas Savage con Cheddar y Panceta', 7200.00, N'Entradas', 0, 0, N'Papas fritas ba' + NCHAR(241) + N'adas en cheddar fundido, panceta crocante y verdeo.'),
    (N'Bastones de Muzzarella', 7800.00, N'Entradas', 1, 0, N'Bastones de muzzarella empanados y fritos, con salsa pomodoro.'),
    (N'Tabla de Picada para 3', 18500.00, N'Entradas', 0, 0, N'Fiambres, quesos, aceitunas, frutos secos y pan casero para compartir.'),
    (N'Burger Cl' + NCHAR(225) + N'sica', 11500.00, N'Principales', 0, 0, N'Medall' + NCHAR(243) + N'n de carne, lechuga, tomate, queso y mayonesa en pan de papa.'),
    (N'Burger Veggie', 11000.00, N'Principales', 1, 0, N'Medall' + NCHAR(243) + N'n de legumbres y vegetales, r' + NCHAR(250) + N'cula, tomate y alioli en pan de papa.'),
    (N'Milanesa con Papas Fritas', 11500.00, N'Principales', 0, 0, N'Milanesa de ternera con porci' + NCHAR(243) + N'n generosa de papas fritas.'),
    (N'Galeto al Lim' + NCHAR(243) + N'n', 13500.00, N'Principales', 0, 0, N'Pollo a la parrilla marinado en lim' + NCHAR(243) + N'n, con ensalada de la casa.'),
    (N'Bife de Chorizo con Papas', 17800.00, N'Principales', 0, 1, N'Bife de chorizo a la parrilla con papas r' + NCHAR(250) + N'sticas. Sin TACC.'),
    (N'Pasta Ravioles de Ricota', 12500.00, N'Principales', 1, 0, N'Ravioles de ricota y nuez con salsa a elecci' + NCHAR(243) + N'n: filetto o crema.'),
    (N'Pasta al Wok con Queso Sardo', 11800.00, N'Principales', 1, 0, N'Fideos salteados al wok con verduras y queso sardo rallado.'),
    (N'Ensalada Caprese', 8200.00, N'Principales', 1, 1, N'Tomate, muzzarella fresca, albahaca y aceite de oliva.'),
    (N'Pizza Napolitana', 12000.00, N'Principales', 1, 0, N'Muzzarella, rodajas de tomate, ajo y albahaca sobre masa casera.'),
    (N'Pizza Fugazzeta', 12500.00, N'Principales', 1, 0, N'Muzzarella y abundante cebolla caramelizada sobre masa casera.'),
    (N'Flan Casero con Dulce de Leche', 5500.00, N'Postres', 1, 1, N'Flan casero con dulce de leche y crema.'),
    (N'Brownie con Helado', 6900.00, N'Postres', 1, 0, N'Brownie de chocolate tibio con una bocha de helado de crema.'),
    (N'Panqueque de Dulce de Leche', 5900.00, N'Postres', 1, 0, N'Panqueque relleno de dulce de leche, flambeado a pedido.'),
    (N'Helado 3 Bochas', 5200.00, N'Postres', 1, 1, N'Tres bochas a elecci' + NCHAR(243) + N'n entre los gustos del d' + NCHAR(237) + N'a.'),
    (N'Agua Mineral 500 ml', 1800.00, N'Bebidas', 1, 1, N'Agua mineral sin gas.'),
    (N'Gaseosa L' + NCHAR(237) + N'nea Coca-Cola 500 ml', 2500.00, N'Bebidas', 0, 0, N'Gaseosa de 500 ml a elecci' + NCHAR(243) + N'n entre las variedades disponibles.'),
    (N'Jugo de Naranja Natural', 3800.00, N'Bebidas', 1, 1, N'Exprimido en el momento.'),
    (N'Limonada con Menta y Jengibre', 3800.00, N'Bebidas', 1, 1, N'Limonada fresca con menta y un toque de jengibre.'),
    (N'Cerveza Rubia Pinta', 4500.00, N'Bebidas', 1, 0, N'Pinta de cerveza rubia tirada, estilo lager.'),
    (N'Cerveza IPA Artesanal Pinta', 4800.00, N'Bebidas', 1, 0, N'Pinta de IPA artesanal, lupulada y de final amargo.'),
    (N'Fernet con Coca', 5500.00, N'Tragos', 1, 1, N'El cl' + NCHAR(225) + N'sico: fernet, Coca-Cola y hielo.'),
    (N'Gin Tonic', 6800.00, N'Tragos', 1, 1, N'Gin, agua t' + NCHAR(243) + N'nica, hielo y rodaja de pepino o c' + NCHAR(237) + N'trico.'),
    (N'Negroni', 7500.00, N'Tragos', 1, 1, N'Gin, Campari y vermut rosso en partes iguales, con piel de naranja.'),
    (N'Mojito', 7200.00, N'Tragos', 1, 1, N'Ron blanco, lima, menta, az' + NCHAR(250) + N'car y soda.'),
    (N'Aperol Spritz', 7200.00, N'Tragos', 1, 1, N'Aperol, espumante y soda, con rodaja de naranja.');

DECLARE @Ins TABLE (Nombre NVARCHAR(100) PRIMARY KEY, TipoMedida NVARCHAR(10) NOT NULL);
INSERT INTO @Ins (Nombre, TipoMedida) VALUES
    (N'Carne picada vacuna', N'Masa'),
    (N'Bife de chorizo', N'Masa'),
    (N'Jamon cocido', N'Masa'),
    (N'Jamon crudo', N'Masa'),
    (N'Salame', N'Masa'),
    (N'Panceta', N'Masa'),
    (N'Queso cheddar', N'Masa'),
    (N'Muzzarella', N'Masa'),
    (N'Provolone', N'Masa'),
    (N'Queso sardo', N'Masa'),
    (N'Queso de picada', N'Masa'),
    (N'Queso parmesano', N'Masa'),
    (N'Ravioles de ricota', N'Masa'),
    (N'Tallarines', N'Masa'),
    (N'Papas', N'Masa'),
    (N'Lechuga', N'Masa'),
    (N'Tomate', N'Masa'),
    (N'Cebolla', N'Masa'),
    (N'Morron', N'Masa'),
    (N'Pepinillos', N'Masa'),
    (N'Salsa Savage', N'Masa'),
    (N'Salsa pomarola envasada', N'Masa'),
    (N'Aceitunas verdes', N'Masa'),
    (N'Pan rallado', N'Masa'),
    (N'Harina 000', N'Masa'),
    (N'Azucar', N'Masa'),
    (N'Chocolate semiamargo', N'Masa'),
    (N'Manteca', N'Masa'),
    (N'Dulce de leche', N'Masa'),
    (N'Helado de crema', N'Masa'),
    (N'Menta', N'Masa'),
    (N'Jengibre', N'Masa'),
    (N'Albahaca', N'Masa'),
    (N'Oregano', N'Masa'),
    (N'Croutons', N'Masa'),
    (N'Aderezo Cesar', N'Masa'),
    (N'Hielo', N'Masa'),
    (N'Aceite de girasol', N'Volumen'),
    (N'Aceite de oliva', N'Volumen'),
    (N'Leche', N'Volumen'),
    (N'Cerveza rubia tirada', N'Volumen'),
    (N'Cerveza IPA tirada', N'Volumen'),
    (N'Fernet', N'Volumen'),
    (N'Gin', N'Volumen'),
    (N'Vermut rojo', N'Volumen'),
    (N'Campari', N'Volumen'),
    (N'Ron blanco', N'Volumen'),
    (N'Aperol', N'Volumen'),
    (N'Espumante', N'Volumen'),
    (N'Agua tonica', N'Volumen'),
    (N'Soda', N'Volumen'),
    (N'Coca-Cola de barra', N'Volumen'),
    (N'Pan burger', N'Unidad'),
    (N'Medallon vegetal', N'Unidad'),
    (N'Huevo', N'Unidad'),
    (N'Tapas de empanada', N'Unidad'),
    (N'Masa de pizza', N'Unidad'),
    (N'Naranja', N'Unidad'),
    (N'Limon', N'Unidad'),
    (N'Coca-Cola 1 L', N'Unidad'),
    (N'Gaseosa 500 ml', N'Unidad'),
    (N'Agua mineral 500 ml', N'Unidad'),
    (N'Milanesa de carne (nalga)', N'Unidad'),
    (N'Medio pollo (galeto)', N'Unidad');

DECLARE @Ing TABLE (Producto NVARCHAR(80) NOT NULL, Insumo NVARCHAR(100) NOT NULL, Cantidad DECIMAL(12,3) NOT NULL, Quitable BIT NOT NULL);
INSERT INTO @Ing (Producto, Insumo, Cantidad, Quitable) VALUES
    (N'Coca-Cola 1L', N'Coca-Cola 1 L', 1, 0),
    (N'Gaseosa L' + NCHAR(237) + N'nea Coca-Cola 500 ml', N'Gaseosa 500 ml', 1, 0),
    (N'Agua Mineral 500 ml', N'Agua mineral 500 ml', 1, 0),
    (N'Jugo de Naranja Natural', N'Naranja', 4, 0),
    (N'Limonada con Menta y Jengibre', N'Limon', 2, 0),
    (N'Limonada con Menta y Jengibre', N'Menta', 5, 1),
    (N'Limonada con Menta y Jengibre', N'Jengibre', 10, 1),
    (N'Limonada con Menta y Jengibre', N'Azucar', 30, 0),
    (N'Limonada con Menta y Jengibre', N'Hielo', 150, 0),
    (N'Limonada con Menta y Jengibre', N'Soda', 250, 0),
    (N'Cerveza Rubia Pinta', N'Cerveza rubia tirada', 473, 0),
    (N'Cerveza IPA Artesanal Pinta', N'Cerveza IPA tirada', 473, 0),
    (N'Fernet con Coca', N'Fernet', 60, 0),
    (N'Fernet con Coca', N'Coca-Cola de barra', 200, 0),
    (N'Fernet con Coca', N'Hielo', 150, 0),
    (N'Gin Tonic', N'Gin', 50, 0),
    (N'Gin Tonic', N'Agua tonica', 150, 0),
    (N'Gin Tonic', N'Hielo', 150, 0),
    (N'Gin Tonic', N'Limon', 1, 1),
    (N'Negroni', N'Gin', 30, 0),
    (N'Negroni', N'Vermut rojo', 30, 0),
    (N'Negroni', N'Campari', 30, 0),
    (N'Negroni', N'Hielo', 120, 0),
    (N'Mojito', N'Ron blanco', 50, 0),
    (N'Mojito', N'Limon', 1, 0),
    (N'Mojito', N'Menta', 8, 1),
    (N'Mojito', N'Azucar', 20, 0),
    (N'Mojito', N'Soda', 60, 0),
    (N'Mojito', N'Hielo', 150, 0),
    (N'Aperol Spritz', N'Aperol', 60, 0),
    (N'Aperol Spritz', N'Espumante', 90, 0),
    (N'Aperol Spritz', N'Soda', 30, 0),
    (N'Aperol Spritz', N'Hielo', 150, 0),
    (N'Flan Casero con Dulce de Leche', N'Huevo', 2, 0),
    (N'Flan Casero con Dulce de Leche', N'Leche', 150, 0),
    (N'Flan Casero con Dulce de Leche', N'Azucar', 40, 0),
    (N'Flan Casero con Dulce de Leche', N'Dulce de leche', 40, 1),
    (N'Brownie con Helado', N'Chocolate semiamargo', 60, 0),
    (N'Brownie con Helado', N'Harina 000', 40, 0),
    (N'Brownie con Helado', N'Manteca', 40, 0),
    (N'Brownie con Helado', N'Huevo', 1, 0),
    (N'Brownie con Helado', N'Azucar', 50, 0),
    (N'Brownie con Helado', N'Helado de crema', 100, 1),
    (N'Panqueque de Dulce de Leche', N'Huevo', 1, 0),
    (N'Panqueque de Dulce de Leche', N'Harina 000', 40, 0),
    (N'Panqueque de Dulce de Leche', N'Leche', 120, 0),
    (N'Panqueque de Dulce de Leche', N'Dulce de leche', 60, 0),
    (N'Panqueque de Dulce de Leche', N'Manteca', 10, 0),
    (N'Helado 3 Bochas', N'Helado de crema', 240, 0),
    (N'Provoleta a la Parrilla', N'Provolone', 200, 0),
    (N'Provoleta a la Parrilla', N'Oregano', 2, 1),
    (N'Provoleta a la Parrilla', N'Aceite de oliva', 10, 0),
    (N'Provoleta a la Parrilla', N'Tomate', 40, 1),
    (N'Empanadas de Carne x3', N'Tapas de empanada', 3, 0),
    (N'Empanadas de Carne x3', N'Carne picada vacuna', 90, 0),
    (N'Empanadas de Carne x3', N'Cebolla', 30, 1),
    (N'Empanadas de Carne x3', N'Aceitunas verdes', 10, 1),
    (N'Papas Savage con Cheddar y Panceta', N'Papas', 300, 0),
    (N'Papas Savage con Cheddar y Panceta', N'Aceite de girasol', 40, 0),
    (N'Papas Savage con Cheddar y Panceta', N'Queso cheddar', 50, 1),
    (N'Papas Savage con Cheddar y Panceta', N'Panceta', 40, 1),
    (N'Bastones de Muzzarella', N'Muzzarella', 200, 0),
    (N'Bastones de Muzzarella', N'Pan rallado', 60, 0),
    (N'Bastones de Muzzarella', N'Huevo', 1, 0),
    (N'Bastones de Muzzarella', N'Harina 000', 20, 0),
    (N'Bastones de Muzzarella', N'Aceite de girasol', 40, 0),
    (N'Bastones de Muzzarella', N'Salsa pomarola envasada', 40, 0),
    (N'Tabla de Picada para 3', N'Jamon crudo', 100, 0),
    (N'Tabla de Picada para 3', N'Salame', 100, 0),
    (N'Tabla de Picada para 3', N'Queso de picada', 150, 0),
    (N'Tabla de Picada para 3', N'Aceitunas verdes', 60, 1),
    (N'Savage Burger Doble', N'Pan burger', 1, 0),
    (N'Savage Burger Doble', N'Carne picada vacuna', 300, 0),
    (N'Savage Burger Doble', N'Queso cheddar', 50, 1),
    (N'Savage Burger Doble', N'Panceta', 40, 1),
    (N'Savage Burger Doble', N'Lechuga', 20, 1),
    (N'Savage Burger Doble', N'Tomate', 30, 1),
    (N'Savage Burger Doble', N'Cebolla', 20, 1),
    (N'Savage Burger Doble', N'Salsa Savage', 30, 1),
    (N'Savage Burger Doble', N'Pepinillos', 15, 1),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Pan burger', 1, 0),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Carne picada vacuna', 150, 0),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Queso cheddar', 25, 1),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Lechuga', 20, 1),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Tomate', 30, 1),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Cebolla', 20, 1),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Salsa Savage', 20, 1),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Pepinillos', 15, 1),
    (N'Burger Veggie', N'Pan burger', 1, 0),
    (N'Burger Veggie', N'Medallon vegetal', 1, 0),
    (N'Burger Veggie', N'Lechuga', 20, 1),
    (N'Burger Veggie', N'Tomate', 30, 1),
    (N'Burger Veggie', N'Cebolla', 20, 1),
    (N'Burger Veggie', N'Salsa Savage', 20, 1),
    (N'Milanesa Napolitana', N'Milanesa de carne (nalga)', 1, 0),
    (N'Milanesa Napolitana', N'Salsa pomarola envasada', 60, 0),
    (N'Milanesa Napolitana', N'Muzzarella', 80, 0),
    (N'Milanesa Napolitana', N'Jamon cocido', 40, 1),
    (N'Milanesa Napolitana', N'Aceite de girasol', 40, 0),
    (N'Milanesa Napolitana', N'Oregano', 1, 1),
    (N'Milanesa con Papas Fritas', N'Milanesa de carne (nalga)', 1, 0),
    (N'Milanesa con Papas Fritas', N'Papas', 300, 0),
    (N'Milanesa con Papas Fritas', N'Aceite de girasol', 60, 0),
    (N'Ensalada C' + NCHAR(233) + N'sar', N'Lechuga', 150, 0),
    (N'Ensalada C' + NCHAR(233) + N'sar', N'Croutons', 30, 1),
    (N'Ensalada C' + NCHAR(233) + N'sar', N'Queso parmesano', 20, 1),
    (N'Ensalada C' + NCHAR(233) + N'sar', N'Aderezo Cesar', 40, 1),
    (N'Pizza Muzzarella', N'Masa de pizza', 1, 0),
    (N'Pizza Muzzarella', N'Salsa pomarola envasada', 100, 0),
    (N'Pizza Muzzarella', N'Muzzarella', 200, 0),
    (N'Pizza Muzzarella', N'Aceitunas verdes', 10, 1),
    (N'Pizza Muzzarella', N'Oregano', 1, 1),
    (N'Pizza Napolitana', N'Masa de pizza', 1, 0),
    (N'Pizza Napolitana', N'Salsa pomarola envasada', 100, 0),
    (N'Pizza Napolitana', N'Muzzarella', 200, 0),
    (N'Pizza Napolitana', N'Tomate', 100, 1),
    (N'Pizza Napolitana', N'Aceitunas verdes', 10, 1),
    (N'Pizza Napolitana', N'Oregano', 1, 1),
    (N'Pizza Fugazzeta', N'Masa de pizza', 1, 0),
    (N'Pizza Fugazzeta', N'Muzzarella', 250, 0),
    (N'Pizza Fugazzeta', N'Cebolla', 150, 0),
    (N'Pizza Fugazzeta', N'Aceitunas verdes', 10, 1),
    (N'Pizza Fugazzeta', N'Oregano', 1, 1),
    (N'Galeto al Lim' + NCHAR(243) + N'n', N'Medio pollo (galeto)', 1, 0),
    (N'Galeto al Lim' + NCHAR(243) + N'n', N'Limon', 1, 1),
    (N'Galeto al Lim' + NCHAR(243) + N'n', N'Aceite de girasol', 20, 0),
    (N'Bife de Chorizo con Papas', N'Bife de chorizo', 350, 0),
    (N'Bife de Chorizo con Papas', N'Papas', 300, 0),
    (N'Bife de Chorizo con Papas', N'Aceite de girasol', 40, 0),
    (N'Pasta Ravioles de Ricota', N'Ravioles de ricota', 300, 0),
    (N'Pasta Ravioles de Ricota', N'Salsa pomarola envasada', 150, 0),
    (N'Pasta Ravioles de Ricota', N'Queso sardo', 20, 1),
    (N'Pasta Ravioles de Ricota', N'Albahaca', 3, 1),
    (N'Pasta al Wok con Queso Sardo', N'Tallarines', 250, 0),
    (N'Pasta al Wok con Queso Sardo', N'Morron', 40, 1),
    (N'Pasta al Wok con Queso Sardo', N'Cebolla', 40, 1),
    (N'Pasta al Wok con Queso Sardo', N'Queso sardo', 40, 1),
    (N'Pasta al Wok con Queso Sardo', N'Aceite de girasol', 20, 0),
    (N'Ensalada Caprese', N'Tomate', 200, 0),
    (N'Ensalada Caprese', N'Muzzarella', 150, 0),
    (N'Ensalada Caprese', N'Albahaca', 5, 1),
    (N'Ensalada Caprese', N'Aceite de oliva', 15, 0);

DECLARE @Ext TABLE (Producto NVARCHAR(80) NOT NULL, Insumo NVARCHAR(100) NOT NULL, Cantidad DECIMAL(12,3) NOT NULL, Precio DECIMAL(10,2) NOT NULL, MaxPorUnidad INT NOT NULL);
INSERT INTO @Ext (Producto, Insumo, Cantidad, Precio, MaxPorUnidad) VALUES
    (N'Savage Burger Doble', N'Queso cheddar', 25, 1200, 3),
    (N'Savage Burger Doble', N'Huevo', 1, 900, 2),
    (N'Savage Burger Doble', N'Salsa Savage', 20, 500, 2),
    (N'Savage Burger Doble', N'Panceta', 20, 1500, 2),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Queso cheddar', 25, 1200, 3),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Huevo', 1, 900, 2),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Salsa Savage', 20, 500, 2),
    (N'Burger Cl' + NCHAR(225) + N'sica', N'Panceta', 20, 1500, 2),
    (N'Burger Veggie', N'Queso cheddar', 25, 1200, 3),
    (N'Burger Veggie', N'Huevo', 1, 900, 2),
    (N'Burger Veggie', N'Salsa Savage', 20, 500, 2),
    (N'Papas Savage con Cheddar y Panceta', N'Queso cheddar', 25, 1200, 2),
    (N'Papas Savage con Cheddar y Panceta', N'Panceta', 20, 1500, 2),
    (N'Pizza Muzzarella', N'Muzzarella', 100, 2500, 2),
    (N'Pizza Muzzarella', N'Aceitunas verdes', 15, 600, 2),
    (N'Pizza Muzzarella', N'Jamon cocido', 40, 1800, 1),
    (N'Pizza Napolitana', N'Muzzarella', 100, 2500, 2),
    (N'Pizza Napolitana', N'Aceitunas verdes', 15, 600, 2),
    (N'Pizza Napolitana', N'Jamon cocido', 40, 1800, 1),
    (N'Pizza Fugazzeta', N'Muzzarella', 100, 2500, 2),
    (N'Pizza Fugazzeta', N'Aceitunas verdes', 15, 600, 2),
    (N'Pizza Fugazzeta', N'Jamon cocido', 40, 1800, 1),
    (N'Pasta Ravioles de Ricota', N'Queso sardo', 20, 900, 3),
    (N'Pasta al Wok con Queso Sardo', N'Queso sardo', 20, 900, 3),
    (N'Milanesa Napolitana', N'Huevo', 1, 900, 2),
    (N'Milanesa con Papas Fritas', N'Huevo', 1, 900, 2),
    (N'Bife de Chorizo con Papas', N'Huevo', 1, 900, 2),
    (N'Ensalada C' + NCHAR(233) + N'sar', N'Queso parmesano', 20, 900, 2);

-- ---------- tablas a vaciar (el orden se resuelve solo con reintentos) ----------
DECLARE @Tablas TABLE (Orden INT IDENTITY(1,1) PRIMARY KEY, Nombre SYSNAME NOT NULL, Hecha BIT NOT NULL DEFAULT 0, Filas INT NULL);
INSERT INTO @Tablas (Nombre)
SELECT v.n FROM (VALUES
    (N'MovimientoCaja'), (N'CajaMoneda'), (N'Caja'),
    (N'PagoEvento'), (N'Pago'), (N'FacturaDetalle'), (N'Factura'),
    (N'PedidoDetalleModificador'), (N'PedidoDetalleExtra'), (N'PedidoDetalleCompartido'), (N'PedidoDetalle'),
    (N'MovimientoStock'), (N'Perdida'), (N'Produccion'),
    (N'ComandaRecibida'), (N'Comensal'), (N'PedidoCabecera'),
    (N'LoteInsumo'), (N'Compra'), (N'InsumoProveedor'), (N'Proveedor'),
    (N'ProductoSugerido'), (N'Especial'), (N'Producto'), (N'Receta'), (N'Insumo')
) v(n)
WHERE OBJECT_ID(N'dbo.' + v.n, N'U') IS NOT NULL;

DECLARE @Usados TABLE (IdInsumo INT PRIMARY KEY);
DECLARE @Plan TABLE (IdInsumo INT PRIMARY KEY, Nombre NVARCHAR(100), TipoMedida NVARCHAR(10), Grupo TINYINT,
                     Elaborado BIT, PorPorcion DECIMAL(12,3), Objetivo DECIMAL(12,3), Vigente DECIMAL(12,3), Falta DECIMAL(12,3));
DECLARE @Prov TABLE (Grupo TINYINT PRIMARY KEY, Nombre NVARCHAR(100), Contacto NVARCHAR(100), Telefono NVARCHAR(30),
                     Email NVARCHAR(120), Direccion NVARCHAR(200), Notas NVARCHAR(300), IdProveedor INT NULL);

INSERT INTO @Prov (Grupo, Nombre, Contacto, Telefono, Email, Direccion, Notas) VALUES
 (1, N'Frigorifico Del Litoral', N'Marcelo Benitez', N'376 4412-780', N'ventas@fdl-litoral.example', N'Av. Quaranta 3150, Posadas',
     N'Carnes, fiambres, lacteos y huevos. Entrega martes y viernes.'),
 (2, N'Verduleria Mayorista Posadas', N'Rosa Acosta', N'376 4455-210', N'pedidos@vmposadas.example', N'Mercado Central, Posadas',
     N'Verduras, frutas y hierbas frescas. Entrega diaria antes de las 8.'),
 (3, N'Distribuidora Almacen y Bebidas', N'Fabian Rojas', N'376 4430-905', N'info@dab-misiones.example', N'Ruta 12 km 7, Posadas',
     N'Secos, salsas, aderezos, gaseosas, cervezas y bebidas. Entrega semanal.');

DECLARE @Tabla SYSNAME, @Filas INT, @Pasada INT = 0, @Progreso BIT, @Mensaje NVARCHAR(500);
DECLARE @SinReceta INT = 0, @Productos INT = 0;

BEGIN TRY
    BEGIN TRANSACTION;

    -- 1. reservas: se sueltan de la sesion de mesa (o se borran)
    IF OBJECT_ID(N'dbo.Reserva', N'U') IS NOT NULL
    BEGIN
        IF @BorrarReservas = 1
            DELETE FROM Reserva;
        ELSE IF COL_LENGTH(N'dbo.Reserva', N'IdPedidoCabecera') IS NOT NULL
            EXEC (N'UPDATE dbo.Reserva SET IdPedidoCabecera = NULL WHERE IdPedidoCabecera IS NOT NULL');
    END
    UPDATE Producto SET IdReceta = NULL WHERE IdReceta IS NOT NULL;
    UPDATE Receta SET IdInsumoProducido = NULL, Rinde = NULL, DiasVencimiento = NULL WHERE IdInsumoProducido IS NOT NULL;   -- el CHECK de elaboracion exige las tres a la vez

    -- 2. se vacian las tablas
    WHILE @Pasada < 12 AND EXISTS (SELECT 1 FROM @Tablas WHERE Hecha = 0)
    BEGIN
        SET @Pasada += 1;
        SET @Progreso = 0;
        DECLARE ct CURSOR LOCAL STATIC FOR SELECT Nombre FROM @Tablas WHERE Hecha = 0 ORDER BY Orden;
        OPEN ct;
        FETCH NEXT FROM ct INTO @Tabla;
        WHILE @@FETCH_STATUS = 0
        BEGIN
            BEGIN TRY
                EXEC (N'DELETE FROM dbo.' + @Tabla);
                SET @Filas = @@ROWCOUNT;
                UPDATE @Tablas SET Hecha = 1, Filas = @Filas WHERE Nombre = @Tabla;
                SET @Progreso = 1;
            END TRY
            BEGIN CATCH
                IF ERROR_NUMBER() <> 547 THROW;
                SET @Mensaje = ERROR_MESSAGE();
            END CATCH;
            FETCH NEXT FROM ct INTO @Tabla;
        END
        CLOSE ct;
        DEALLOCATE ct;
        IF @Progreso = 0 BREAK;
    END
    IF EXISTS (SELECT 1 FROM @Tablas WHERE Hecha = 0)
    BEGIN
        SELECT @Tabla = MIN(Nombre) FROM @Tablas WHERE Hecha = 0;
        SET @Mensaje = N'No se pudo vaciar la tabla ' + @Tabla + N': otra tabla la referencia. ' + ISNULL(@Mensaje, N'');
        THROW 50001, @Mensaje, 1;
    END
    UPDATE Mesa SET Estado = 0 WHERE Estado <> 0;

    -- 3. carta: categorias (las que falten) y productos
    INSERT INTO Categoria (Nombre)
    SELECT DISTINCT p.Categoria FROM @Prod p WHERE NOT EXISTS (SELECT 1 FROM Categoria c WHERE c.Nombre = p.Categoria);

    INSERT INTO Producto (Nombre, PrecioActual, IdCategoria, EsVegetariano, AptoCeliaco, Activo, Descripcion)
    SELECT p.Nombre, p.Precio, c.Id, p.Veg, p.Cel, 1, p.Descripcion FROM @Prod p JOIN Categoria c ON c.Nombre = p.Categoria;

    UPDATE p
    SET p.TiempoEstimadoMin = CASE
            WHEN p.Nombre = N'Coca-Cola 1L' THEN 2
            WHEN p.Nombre LIKE N'Agua%' THEN 2
            WHEN p.Nombre LIKE N'Jugo%' OR p.Nombre LIKE N'Limonada%' THEN 5
            WHEN p.Nombre LIKE N'Pizza%' OR p.Nombre LIKE N'Milanesa%' THEN 25
            WHEN p.Nombre LIKE N'Galeto%' OR p.Nombre LIKE N'Bife%' THEN 30
            WHEN p.Nombre LIKE N'Ensalada%' THEN 10
            WHEN p.Nombre LIKE N'Empanadas%' OR p.Nombre LIKE N'Tabla%' THEN 15
            WHEN c.Nombre = N'Bebidas' THEN 3
            WHEN c.Nombre = N'Tragos' THEN 6
            WHEN c.Nombre = N'Entradas' THEN 12
            WHEN c.Nombre = N'Postres' THEN 6
            ELSE 20 END,
        p.Porciones = CASE
            WHEN p.Nombre = N'Coca-Cola 1L' THEN 4
            WHEN p.Nombre LIKE N'Tabla%' THEN 3
            WHEN p.Nombre LIKE N'Pizza%' OR p.Nombre LIKE N'Provoleta%' OR p.Nombre LIKE N'Papas%' OR p.Nombre LIKE N'Bastones%' THEN 2
            ELSE 1 END
    FROM Producto p JOIN Categoria c ON c.Id = p.IdCategoria;

    -- 4. insumos, recetas, ingredientes, extras y vinculo con el producto
    INSERT INTO Insumo (Nombre, TipoMedida) SELECT Nombre, TipoMedida FROM @Ins;
    INSERT INTO Receta (Nombre) SELECT N'Receta ' + Nombre FROM @Prod;
    INSERT INTO RecetaIngrediente (IdReceta, IdInsumo, Cantidad, EsQuitable)
    SELECT r.Id, i.Id, g.Cantidad, g.Quitable
    FROM @Ing g JOIN Receta r ON r.Nombre = N'Receta ' + g.Producto JOIN Insumo i ON i.Nombre = g.Insumo;
    INSERT INTO RecetaExtra (IdReceta, IdInsumo, Cantidad, Precio, MaxPorUnidad)
    SELECT r.Id, i.Id, e.Cantidad, e.Precio, e.MaxPorUnidad
    FROM @Ext e JOIN Receta r ON r.Nombre = N'Receta ' + e.Producto JOIN Insumo i ON i.Nombre = e.Insumo;
    UPDATE p SET IdReceta = r.Id FROM Producto p JOIN Receta r ON r.Nombre = N'Receta ' + p.Nombre;

    SELECT @Productos = COUNT(*), @SinReceta = SUM(CASE WHEN IdReceta IS NULL THEN 1 ELSE 0 END) FROM Producto;
    IF @SinReceta > 0 OR @Productos <> (SELECT COUNT(*) FROM @Prod)
        THROW 50002, N'La carta no quedo completa: hay productos sin receta. Se deshace todo.', 1;

    -- 5. stock realista: insumos de las recetas, objetivo, proveedores, compras y lotes

    INSERT INTO @Usados
    SELECT ri.IdInsumo FROM Producto p JOIN RecetaIngrediente ri ON ri.IdReceta = p.IdReceta
    WHERE p.Activo = 1 AND p.Nombre NOT LIKE N'ZZ %'
    UNION
    SELECT re.IdInsumo FROM Producto p JOIN RecetaExtra re ON re.IdReceta = p.IdReceta
    WHERE p.Activo = 1 AND p.Nombre NOT LIKE N'ZZ %';
    DECLARE @Vuelta INT = 0;
    WHILE @Vuelta < 2
    BEGIN
        INSERT INTO @Usados
        SELECT DISTINCT ri.IdInsumo
        FROM Receta r JOIN RecetaIngrediente ri ON ri.IdReceta = r.Id
        WHERE r.IdInsumoProducido IN (SELECT IdInsumo FROM @Usados)
          AND ri.IdInsumo NOT IN (SELECT IdInsumo FROM @Usados);
        SET @Vuelta += 1;
    END
    INSERT INTO @Plan (IdInsumo, Nombre, TipoMedida, Grupo, Elaborado, PorPorcion, Objetivo, Vigente, Falta)
    SELECT i.Id, i.Nombre, i.TipoMedida, g.Grupo, e.Elaborado, c.PorPorcion, o.Objetivo, ISNULL(s.Vigente, 0), o.Objetivo - ISNULL(s.Vigente, 0)
    FROM Insumo i
    JOIN @Usados u ON u.IdInsumo = i.Id
    CROSS APPLY (SELECT CASE
            WHEN i.Nombre LIKE N'%carne%' OR i.Nombre LIKE N'%bife%' OR i.Nombre LIKE N'%lomo%' OR i.Nombre LIKE N'%hamburguesa%'
              OR i.Nombre LIKE N'%medall%' OR i.Nombre LIKE N'%pollo%' OR i.Nombre LIKE N'%cerdo%' OR i.Nombre LIKE N'%costilla%'
              OR i.Nombre LIKE N'%chorizo%' OR i.Nombre LIKE N'%panceta%' OR i.Nombre LIKE N'%bacon%' OR i.Nombre LIKE N'%tocino%'
              OR i.Nombre LIKE N'%jamon%' OR i.Nombre LIKE N'%salame%' OR i.Nombre LIKE N'%pescado%' OR i.Nombre LIKE N'%salmon%'
              OR i.Nombre LIKE N'%camaron%' OR i.Nombre LIKE N'%queso%' OR i.Nombre LIKE N'%muzza%' OR i.Nombre LIKE N'%cheddar%'
              OR i.Nombre LIKE N'%leche%' OR i.Nombre LIKE N'%crema%' OR i.Nombre LIKE N'%manteca%' OR i.Nombre LIKE N'%huevo%'
              OR i.Nombre LIKE N'%ricota%' OR i.Nombre LIKE N'%provolone%' OR i.Nombre LIKE N'%yogur%' THEN 1
            WHEN i.Nombre LIKE N'%tomate%' OR i.Nombre LIKE N'%lechuga%' OR i.Nombre LIKE N'%cebolla%' OR i.Nombre LIKE N'%papa%'
              OR i.Nombre LIKE N'%batata%' OR i.Nombre LIKE N'%morron%' OR i.Nombre LIKE N'%ajo%' OR i.Nombre LIKE N'%limon%'
              OR i.Nombre LIKE N'%naranja%' OR i.Nombre LIKE N'%palta%' OR i.Nombre LIKE N'%zanahoria%' OR i.Nombre LIKE N'%rucula%'
              OR i.Nombre LIKE N'%albahaca%' OR i.Nombre LIKE N'%perejil%' OR i.Nombre LIKE N'%menta%' OR i.Nombre LIKE N'%pepino%'
              OR i.Nombre LIKE N'%hongo%' OR i.Nombre LIKE N'%champi%' OR i.Nombre LIKE N'%verdeo%' OR i.Nombre LIKE N'%frutilla%'
              OR i.Nombre LIKE N'%banana%' OR i.Nombre LIKE N'%manzana%' OR i.Nombre LIKE N'%lima%' OR i.Nombre LIKE N'%jengibre%'
              OR i.Nombre LIKE N'%espinaca%' OR i.Nombre LIKE N'%choclo%' OR i.Nombre LIKE N'%calabaza%' OR i.Nombre LIKE N'%zapallo%'
              OR i.Nombre LIKE N'%berenjena%' OR i.Nombre LIKE N'%romero%' OR i.Nombre LIKE N'%cilantro%' THEN 2
            ELSE 3 END AS Grupo) g
    CROSS APPLY (SELECT CASE WHEN EXISTS (SELECT 1 FROM Receta r WHERE r.IdInsumoProducido = i.Id) THEN CAST(1 AS BIT) ELSE CAST(0 AS BIT) END AS Elaborado) e
    CROSS APPLY (SELECT ISNULL((SELECT MAX(x.Cantidad) FROM (
                        SELECT Cantidad FROM RecetaIngrediente WHERE IdInsumo = i.Id
                        UNION ALL
                        SELECT Cantidad FROM RecetaExtra WHERE IdInsumo = i.Id) x), CASE i.TipoMedida WHEN N'Unidad' THEN 1 ELSE 100 END) AS PorPorcion) c
    CROSS APPLY (SELECT CASE i.TipoMedida
            WHEN N'Unidad' THEN CAST(CASE WHEN CEILING(c.PorPorcion * CASE g.Grupo WHEN 3 THEN @PorcionesAlmacen ELSE @PorcionesFrescos END / 6.0) * 6 < 12
                                           THEN 12
                                           ELSE CEILING(c.PorPorcion * CASE g.Grupo WHEN 3 THEN @PorcionesAlmacen ELSE @PorcionesFrescos END / 6.0) * 6 END AS DECIMAL(12,3))
            ELSE CAST(CASE WHEN CEILING(c.PorPorcion * CASE g.Grupo WHEN 3 THEN @PorcionesAlmacen ELSE @PorcionesFrescos END / 500.0) * 500 < 500
                           THEN 500
                           ELSE CEILING(c.PorPorcion * CASE g.Grupo WHEN 3 THEN @PorcionesAlmacen ELSE @PorcionesFrescos END / 500.0) * 500 END AS DECIMAL(12,3))
            END AS Objetivo) o
    OUTER APPLY (SELECT SUM(l.CantidadActual) AS Vigente FROM LoteInsumo l
                 WHERE l.IdInsumo = i.Id AND l.Estado = N'Activo' AND (l.FechaVencimiento IS NULL OR l.FechaVencimiento >= @Hoy)) s
    WHERE i.Activo = 1 AND i.Nombre NOT LIKE N'ZZ %' AND i.Nombre NOT LIKE N'% Extras [0-9]%'
      AND ISNULL(s.Vigente, 0) < o.Objetivo * 0.5;

    -- proveedores (se reusan si ya existen con ese nombre)
    UPDATE p SET IdProveedor = x.Id FROM @Prov p JOIN Proveedor x ON x.Nombre = p.Nombre;
    INSERT INTO Proveedor (Nombre, Contacto, Telefono, Email, Direccion, Notas)
    SELECT Nombre, Contacto, Telefono, Email, Direccion, Notas FROM @Prov WHERE IdProveedor IS NULL;
    UPDATE p SET IdProveedor = x.Id FROM @Prov p JOIN Proveedor x ON x.Nombre = p.Nombre WHERE p.IdProveedor IS NULL;

    -- vinculo insumo-proveedor (un principal por insumo) y objetivo del semaforo, para todos los insumos usados
    INSERT INTO InsumoProveedor (IdInsumo, IdProveedor, EsPrincipal)
    SELECT p.IdInsumo, pr.IdProveedor, 1
    FROM @Plan p JOIN @Prov pr ON pr.Grupo = p.Grupo
    WHERE p.Elaborado = 0
      AND NOT EXISTS (SELECT 1 FROM InsumoProveedor ip WHERE ip.IdInsumo = p.IdInsumo AND ip.EsPrincipal = 1)
      AND NOT EXISTS (SELECT 1 FROM InsumoProveedor ip WHERE ip.IdInsumo = p.IdInsumo AND ip.IdProveedor = pr.IdProveedor);
    UPDATE i SET StockObjetivo = p.Objetivo FROM Insumo i JOIN @Plan p ON p.IdInsumo = i.Id;

    DECLARE @Lotes TABLE (IdLote INT, Cantidad DECIMAL(12,3), Origen NVARCHAR(12));
    DECLARE @Grupo TINYINT, @IdProv INT, @Compra INT;

    -- una compra por proveedor; los elaborados van como ajuste, sin compra
    DECLARE cg CURSOR LOCAL FAST_FORWARD FOR SELECT Grupo, IdProveedor FROM @Prov ORDER BY Grupo;
    OPEN cg; FETCH NEXT FROM cg INTO @Grupo, @IdProv;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        IF EXISTS (SELECT 1 FROM @Plan WHERE Grupo = @Grupo AND Elaborado = 0)
        BEGIN
            INSERT INTO Compra (IdProveedor, IdEmpleado, Nota) VALUES (@IdProv, @Gerente, N'Stock inicial de la demo');
            SET @Compra = SCOPE_IDENTITY();

            IF @Grupo IN (1, 2)
            BEGIN
                -- perecederos: lote A (60%) vence antes, lote B (40%) vence despues
                INSERT INTO LoteInsumo (IdInsumo, IdCompra, Origen, FechaVencimiento, CantidadInicial, CantidadActual, CostoUnitario, Estado)
                OUTPUT inserted.Id, inserted.CantidadInicial, inserted.Origen INTO @Lotes (IdLote, Cantidad, Origen)
                SELECT IdInsumo, @Compra, N'Compra', DATEADD(DAY, CASE @Grupo WHEN 1 THEN 6 ELSE 4 END, @Hoy),
                       ROUND(Falta * 0.6, 0), ROUND(Falta * 0.6, 0), 0.01, N'Activo'
                FROM @Plan WHERE Grupo = @Grupo AND Elaborado = 0 AND ROUND(Falta * 0.6, 0) > 0;
                INSERT INTO LoteInsumo (IdInsumo, IdCompra, Origen, FechaVencimiento, CantidadInicial, CantidadActual, CostoUnitario, Estado)
                OUTPUT inserted.Id, inserted.CantidadInicial, inserted.Origen INTO @Lotes (IdLote, Cantidad, Origen)
                SELECT IdInsumo, @Compra, N'Compra', DATEADD(DAY, CASE @Grupo WHEN 1 THEN 12 ELSE 9 END, @Hoy),
                       Falta - ROUND(Falta * 0.6, 0), Falta - ROUND(Falta * 0.6, 0), 0.01, N'Activo'
                FROM @Plan WHERE Grupo = @Grupo AND Elaborado = 0 AND Falta - ROUND(Falta * 0.6, 0) > 0;
            END
            ELSE
            BEGIN
                INSERT INTO LoteInsumo (IdInsumo, IdCompra, Origen, FechaVencimiento, CantidadInicial, CantidadActual, CostoUnitario, Estado)
                OUTPUT inserted.Id, inserted.CantidadInicial, inserted.Origen INTO @Lotes (IdLote, Cantidad, Origen)
                SELECT IdInsumo, @Compra, N'Compra', DATEADD(DAY, 120, @Hoy), Falta, Falta, 0.01, N'Activo'
                FROM @Plan WHERE Grupo = @Grupo AND Elaborado = 0 AND Falta > 0;
            END
        END
        FETCH NEXT FROM cg INTO @Grupo, @IdProv;
    END
    CLOSE cg; DEALLOCATE cg;

    INSERT INTO MovimientoStock (IdLote, Tipo, Cantidad, IdEmpleado, Nota)
    SELECT IdLote, N'Compra', Cantidad, @Gerente, N'Stock inicial de la demo' FROM @Lotes WHERE Origen = N'Compra';

    -- elaborados en el local: lote de ajuste, sin proveedor ni compra, vence en 5 dias
    DECLARE @LotesAj TABLE (IdLote INT, Cantidad DECIMAL(12,3));
    INSERT INTO LoteInsumo (IdInsumo, IdCompra, Origen, FechaVencimiento, CantidadInicial, CantidadActual, CostoUnitario, Estado)
    OUTPUT inserted.Id, inserted.CantidadInicial INTO @LotesAj (IdLote, Cantidad)
    SELECT IdInsumo, NULL, N'Ajuste', DATEADD(DAY, 5, @Hoy), Falta, Falta, 0.01, N'Activo'
    FROM @Plan WHERE Elaborado = 1 AND Falta > 0;
    INSERT INTO MovimientoStock (IdLote, Tipo, Cantidad, IdEmpleado, Nota)
    SELECT IdLote, N'Ajuste', Cantidad, @Gerente, N'Stock inicial de la demo (elaboracion propia)' FROM @LotesAj;

    IF @Aplicar = 1
    BEGIN
        COMMIT TRANSACTION;
        PRINT N'APLICADO: la demo quedo armada. Esperar 1 minuto (cache del menu) o reiniciar runserver.';
    END
    ELSE
    BEGIN
        ROLLBACK TRANSACTION;
        PRINT N'ENSAYO: no se cambio nada. Si el informe te cierra, poner @Aplicar = 1 y ejecutar de nuevo.';
    END
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    PRINT N'ERROR, se deshizo todo (no se cambio nada): ' + ERROR_MESSAGE();
    SELECT N'ERROR - SE DESHIZO TODO, NO SE CAMBIO NADA' AS Estado, ERROR_NUMBER() AS Numero, ERROR_LINE() AS Linea, ERROR_MESSAGE() AS Detalle;
END CATCH;

-- ---------- informe ----------
SELECT N'Tablas vaciadas' AS Informe, Nombre AS Detalle, Filas AS Cantidad FROM @Tablas ORDER BY Orden;
SELECT CASE p.Grupo WHEN 1 THEN N'Frigorifico Del Litoral' WHEN 2 THEN N'Verduleria Mayorista Posadas' ELSE N'Distribuidora Almacen y Bebidas' END AS Proveedor,
       CASE WHEN p.Elaborado = 1 THEN N'(elaboracion propia)' ELSE N'' END AS Nota,
       p.Nombre AS Insumo, p.TipoMedida, p.PorPorcion AS GastaUnaPorcion, p.Objetivo AS StockObjetivo, p.Falta AS StockCargado
FROM @Plan p ORDER BY p.Grupo, p.Nombre;
SELECT (SELECT COUNT(*) FROM Producto) AS Productos, (SELECT COUNT(*) FROM Receta) AS Recetas,
       (SELECT COUNT(*) FROM RecetaIngrediente) AS Ingredientes, (SELECT COUNT(*) FROM RecetaExtra) AS Extras,
       (SELECT COUNT(*) FROM Insumo) AS Insumos, (SELECT COUNT(*) FROM Proveedor) AS Proveedores, (SELECT COUNT(*) FROM LoteInsumo) AS Lotes;
-- nota: con @Aplicar = 0 este ultimo conteo sale en 0 porque el ensayo deshizo todo; el listado de arriba muestra lo que se habria cargado

