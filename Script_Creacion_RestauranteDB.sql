-- 1. Creación de la base de datos
CREATE DATABASE RestauranteDB;
GO

USE RestauranteDB;
GO

-- 2. Creación de Tablas Independientes
CREATE TABLE Mesa (
    Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    Numero INT NOT NULL,
    CapacidadMaxima INT NOT NULL
);
GO

CREATE TABLE Mozo (
    Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    Nombre NVARCHAR(80) NOT NULL,
    Apellido NVARCHAR(80) NOT NULL
);
GO

CREATE TABLE Producto (
    Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    Nombre NVARCHAR(80) NOT NULL,
    PrecioActual DECIMAL(10,2) NOT NULL,
    Categoria NVARCHAR(50) NOT NULL
);
GO

-- 3. Creación de Tablas Dependientes (Con Claves Foráneas)
CREATE TABLE PedidoCabecera (
    Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    IdMesa INT NOT NULL FOREIGN KEY REFERENCES Mesa(Id),
    IdMozo INT NOT NULL FOREIGN KEY REFERENCES Mozo(Id),
    FechaHoraApertura DATETIME NOT NULL,
    FechaHoraCierre DATETIME NOT NULL,
    CantidadComensales INT NOT NULL,
    Estado NVARCHAR(20) NOT NULL
);
GO

CREATE TABLE PedidoDetalle (
    Id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    IdPedidoCabecera INT NOT NULL FOREIGN KEY REFERENCES PedidoCabecera(Id),
    IdProducto INT NOT NULL FOREIGN KEY REFERENCES Producto(Id),
    Cantidad INT NOT NULL,
    SubTotal DECIMAL(10,2) NOT NULL
);
GO

-- 4. Carga de Datos de Prueba
INSERT INTO Mesa (Numero, CapacidadMaxima) VALUES (1, 4), (2, 2), (3, 6);
INSERT INTO Mozo (Nombre, Apellido) VALUES ('Gonzalo', 'Viarengo'), ('David', 'Noguera');
INSERT INTO Producto (Nombre, PrecioActual, Categoria) 
VALUES 
('Milanesa con Papas', 8500.00, 'Plato Principal'),
('Coca Cola 1.5L', 2200.00, 'Bebida'),
('Flan Mixto', 3000.00, 'Postre');
GO