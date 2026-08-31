-- =========================================================
-- RestauranteDB — Script de creación (v2, AE1 ampliado)
-- =========================================================

CREATE TABLE Rol (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    Nombre NVARCHAR(30) NOT NULL
);

CREATE TABLE Empleado (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    Nombre NVARCHAR(80) NOT NULL,
    Apellido NVARCHAR(80) NOT NULL,
    IdRol INT NOT NULL,
    Usuario NVARCHAR(50) NOT NULL UNIQUE,
    ContraseñaHash NVARCHAR(256) NOT NULL,
    Activo BIT NOT NULL DEFAULT 1,
    FechaIngreso DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT FK_Empleado_Rol FOREIGN KEY (IdRol) REFERENCES Rol(Id)
);

CREATE TABLE Mesa (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    Numero INT NOT NULL,
    CapacidadMaxima INT NOT NULL,
    Estado BIT NOT NULL DEFAULT 0
);

CREATE TABLE Categoria (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    Nombre NVARCHAR(50) NOT NULL
);

CREATE TABLE Producto (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    Nombre NVARCHAR(80) NOT NULL,
    PrecioActual DECIMAL(10,2) NOT NULL,
    IdCategoria INT NOT NULL,
    EsVegetariano BIT NOT NULL DEFAULT 0,
    AptoCeliaco BIT NOT NULL DEFAULT 0,
    Activo BIT NOT NULL DEFAULT 1,
    CONSTRAINT FK_Producto_Categoria FOREIGN KEY (IdCategoria) REFERENCES Categoria(Id)
);

CREATE TABLE ProductoSugerido (
    IdProducto INT NOT NULL,
    IdProductoSugerido INT NOT NULL,
    CONSTRAINT PK_ProductoSugerido PRIMARY KEY (IdProducto, IdProductoSugerido),
    CONSTRAINT FK_ProdSug_Producto FOREIGN KEY (IdProducto) REFERENCES Producto(Id),
    CONSTRAINT FK_ProdSug_Sugerido FOREIGN KEY (IdProductoSugerido) REFERENCES Producto(Id)
);

CREATE TABLE PedidoCabecera (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    IdMesa INT NOT NULL,
    IdEmpleado INT NOT NULL,
    CodigoPin CHAR(4) NOT NULL,
    FechaHoraApertura DATETIME NOT NULL DEFAULT GETDATE(),
    FechaHoraCierre DATETIME NULL,
    CantidadComensales INT NOT NULL,
    Estado NVARCHAR(20) NOT NULL DEFAULT 'Abierto',
    CONSTRAINT FK_PedidoCab_Mesa FOREIGN KEY (IdMesa) REFERENCES Mesa(Id),
    CONSTRAINT FK_PedidoCab_Empleado FOREIGN KEY (IdEmpleado) REFERENCES Empleado(Id)
);

CREATE TABLE PedidoDetalle (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    IdPedidoCabecera INT NOT NULL,
    IdProducto INT NOT NULL,
    Cantidad INT NOT NULL,
    PrecioUnitario DECIMAL(10,2) NOT NULL,
    SubTotal DECIMAL(10,2) NOT NULL,
    IdentificadorComensal NVARCHAR(50) NULL,
    EstadoCocina BIT NOT NULL DEFAULT 0,
    CONSTRAINT FK_PedidoDet_Cabecera FOREIGN KEY (IdPedidoCabecera) REFERENCES PedidoCabecera(Id),
    CONSTRAINT FK_PedidoDet_Producto FOREIGN KEY (IdProducto) REFERENCES Producto(Id)
);

CREATE TABLE Reserva (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    Nombre NVARCHAR(80) NOT NULL,
    Apellido NVARCHAR(80) NOT NULL,
    Telefono NVARCHAR(20) NOT NULL,
    Fecha DATE NOT NULL,
    Hora TIME NOT NULL,
    IdMesa INT NULL,
    IdEmpleado INT NOT NULL,
    Estado NVARCHAR(20) NOT NULL DEFAULT 'Confirmada',
    CONSTRAINT FK_Reserva_Mesa FOREIGN KEY (IdMesa) REFERENCES Mesa(Id),
    CONSTRAINT FK_Reserva_Empleado FOREIGN KEY (IdEmpleado) REFERENCES Empleado(Id)
);

CREATE TABLE MetodoPago (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    Nombre NVARCHAR(30) NOT NULL
);

CREATE TABLE Factura (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    IdPedidoCabecera INT NOT NULL,
    FechaHoraEmision DATETIME NOT NULL DEFAULT GETDATE(),
    Total DECIMAL(10,2) NOT NULL,
    SolicitoTicket BIT NOT NULL DEFAULT 0,
    CambioEntregado DECIMAL(10,2) NULL,
    TotalUSD DECIMAL(10,2) NOT NULL,
    TotalBRL DECIMAL(10,2) NOT NULL,
    TotalPYG DECIMAL(10,2) NOT NULL,
    CONSTRAINT FK_Factura_PedidoCab FOREIGN KEY (IdPedidoCabecera) REFERENCES PedidoCabecera(Id)
);

CREATE TABLE Pago (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    IdFactura INT NOT NULL,
    IdMetodoPago INT NOT NULL,
    Monto DECIMAL(10,2) NOT NULL,
    ReferenciaExterna NVARCHAR(100) NULL,
    FechaHora DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT FK_Pago_Factura FOREIGN KEY (IdFactura) REFERENCES Factura(Id),
    CONSTRAINT FK_Pago_MetodoPago FOREIGN KEY (IdMetodoPago) REFERENCES MetodoPago(Id)
);

CREATE TABLE CotizacionMoneda (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    Moneda NVARCHAR(3) NOT NULL,
    Valor DECIMAL(10,4) NOT NULL,
    Fecha DATE NOT NULL
);

CREATE TABLE Caja (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    IdEmpleadoApertura INT NOT NULL,
    FechaHoraApertura DATETIME NOT NULL DEFAULT GETDATE(),
    MontoApertura DECIMAL(10,2) NOT NULL,
    IdEmpleadoCierre INT NULL,
    FechaHoraCierre DATETIME NULL,
    MontoCierre DECIMAL(10,2) NULL,
    Estado NVARCHAR(20) NOT NULL DEFAULT 'Abierta',
    CONSTRAINT FK_Caja_EmpleadoApertura FOREIGN KEY (IdEmpleadoApertura) REFERENCES Empleado(Id),
    CONSTRAINT FK_Caja_EmpleadoCierre FOREIGN KEY (IdEmpleadoCierre) REFERENCES Empleado(Id)
);

CREATE TABLE MovimientoCaja (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    IdCaja INT NOT NULL,
    Tipo NVARCHAR(20) NOT NULL,
    Monto DECIMAL(10,2) NOT NULL,
    Descripcion NVARCHAR(200) NULL,
    FechaHora DATETIME NOT NULL DEFAULT GETDATE(),
    IdEmpleado INT NOT NULL,
    IdPago INT NULL,
    CONSTRAINT FK_MovCaja_Caja FOREIGN KEY (IdCaja) REFERENCES Caja(Id),
    CONSTRAINT FK_MovCaja_Empleado FOREIGN KEY (IdEmpleado) REFERENCES Empleado(Id),
    CONSTRAINT FK_MovCaja_Pago FOREIGN KEY (IdPago) REFERENCES Pago(Id)
);