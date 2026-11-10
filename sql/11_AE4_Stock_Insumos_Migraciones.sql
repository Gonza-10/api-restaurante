USE RestauranteDB;
GO

-- Stock, hito 1: proveedores, insumos, compras, lotes y libro de movimientos.
--
-- Como se relacionan (la "rueda" del stock):
--   Proveedor  -> a quien se le compra. Un insumo puede tener varios proveedores (InsumoProveedor).
--   Insumo     -> la materia prima (harina, tomate, gaseosa). Se mide siempre en UNIDAD BASE segun su TipoMedida:
--                 Masa = gramos, Volumen = mililitros, Unidad = unidades. Kilos y litros son solo visualizacion.
--   Compra     -> una compra a un proveedor (cabecera). Cada linea de la compra genera un LoteInsumo.
--   LoteInsumo -> lo que entro en UNA compra para UN insumo: cantidad, costo por unidad base y vencimiento.
--                 El tamano de la bolsa se define en cada compra (10 bolsas de 15 kg un mes, de 10 kg otro).
--                 Se consume por FEFO: primero el que vence antes.
--   MovimientoStock -> libro de movimientos: TODO cambio de cantidad de un lote deja una fila (cantidad con signo).
--
-- Reglas que garantiza la base (no solo la API):
--   * No existe stock negativo: CantidadActual >= 0. Es la defensa final contra dos comandas que compiten por lo ultimo.
--   * La cantidad actual de un lote nunca supera la inicial.
--   * La suma de los movimientos de un lote es siempre igual a su CantidadActual (lo verifica la API y un test).
--   * El stock de un insumo NO se guarda en una columna: es la suma de sus lotes activos (vw_StockInsumo).
--
-- Fuera de este hito (los agregan los scripts siguientes): recetas y sub-recetas, motivos de perdida, elaboracion.
-- Es idempotente: se puede ejecutar mas de una vez.

-- ---------- Proveedor ----------
IF OBJECT_ID('dbo.Proveedor', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Proveedor (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Proveedor PRIMARY KEY,
        Nombre NVARCHAR(100) NOT NULL,
        Contacto NVARCHAR(100) NULL,           -- persona de contacto
        Telefono NVARCHAR(30) NULL,
        Email NVARCHAR(120) NULL,
        Direccion NVARCHAR(200) NULL,
        Notas NVARCHAR(300) NULL,
        Activo BIT NOT NULL CONSTRAINT DF_Proveedor_Activo DEFAULT 1,   -- baja logica: conserva el historial de compras
        CONSTRAINT UQ_Proveedor_Nombre UNIQUE (Nombre)
    );
END
GO

-- ---------- Insumo ----------
IF OBJECT_ID('dbo.Insumo', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Insumo (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Insumo PRIMARY KEY,
        Nombre NVARCHAR(100) NOT NULL,
        TipoMedida NVARCHAR(10) NOT NULL,      -- Masa (g) / Volumen (ml) / Unidad (u): todo se guarda en la unidad base
        StockObjetivo DECIMAL(12,3) NOT NULL CONSTRAINT DF_Insumo_StockObjetivo DEFAULT 0,   -- lo que seria el 100% (0 = sin definir)
        UmbralBajoPct TINYINT NOT NULL CONSTRAINT DF_Insumo_UmbralBajo DEFAULT 50,           -- amarillo: igual o menor a este % del objetivo
        UmbralCriticoPct TINYINT NOT NULL CONSTRAINT DF_Insumo_UmbralCritico DEFAULT 20,     -- rojo: igual o menor a este %
        Activo BIT NOT NULL CONSTRAINT DF_Insumo_Activo DEFAULT 1,
        CONSTRAINT UQ_Insumo_Nombre UNIQUE (Nombre),
        CONSTRAINT CK_Insumo_TipoMedida CHECK (TipoMedida IN (N'Masa', N'Volumen', N'Unidad')),
        CONSTRAINT CK_Insumo_StockObjetivo CHECK (StockObjetivo >= 0),
        CONSTRAINT CK_Insumo_Umbrales CHECK (UmbralCriticoPct < UmbralBajoPct AND UmbralBajoPct <= 100)
    );
END
GO

-- ---------- InsumoProveedor (un insumo puede comprarse a varios proveedores) ----------
IF OBJECT_ID('dbo.InsumoProveedor', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.InsumoProveedor (
        IdInsumo INT NOT NULL CONSTRAINT FK_InsumoProveedor_Insumo FOREIGN KEY REFERENCES dbo.Insumo (Id),
        IdProveedor INT NOT NULL CONSTRAINT FK_InsumoProveedor_Proveedor FOREIGN KEY REFERENCES dbo.Proveedor (Id),
        EsPrincipal BIT NOT NULL CONSTRAINT DF_InsumoProveedor_EsPrincipal DEFAULT 0,   -- el que se sugiere en la lista de reposicion
        CONSTRAINT PK_InsumoProveedor PRIMARY KEY (IdInsumo, IdProveedor)
    );
END
GO

-- A lo sumo un proveedor principal por insumo
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UQ_InsumoProveedor_Principal' AND object_id = OBJECT_ID('dbo.InsumoProveedor')
)
    CREATE UNIQUE INDEX UQ_InsumoProveedor_Principal ON dbo.InsumoProveedor (IdInsumo) WHERE EsPrincipal = 1;
GO

-- ---------- Compra (cabecera) ----------
-- El total de la compra no se guarda: es la suma de sus lotes (cantidad inicial x costo unitario).
IF OBJECT_ID('dbo.Compra', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Compra (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Compra PRIMARY KEY,
        IdProveedor INT NOT NULL CONSTRAINT FK_Compra_Proveedor FOREIGN KEY REFERENCES dbo.Proveedor (Id),
        FechaHora DATETIME NOT NULL CONSTRAINT DF_Compra_FechaHora DEFAULT GETDATE(),
        IdEmpleado INT NOT NULL CONSTRAINT FK_Compra_Empleado FOREIGN KEY REFERENCES dbo.Empleado (Id),
        IdJornada INT NULL CONSTRAINT FK_Compra_Jornada FOREIGN KEY REFERENCES dbo.Jornada (Id),   -- NULL: compra hecha sin jornada abierta
        NumeroComprobante NVARCHAR(50) NULL,
        Nota NVARCHAR(300) NULL
    );
END
GO

-- ---------- LoteInsumo ----------
IF OBJECT_ID('dbo.LoteInsumo', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.LoteInsumo (
        Id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_LoteInsumo PRIMARY KEY,
        IdInsumo INT NOT NULL CONSTRAINT FK_LoteInsumo_Insumo FOREIGN KEY REFERENCES dbo.Insumo (Id),
        IdCompra INT NULL CONSTRAINT FK_LoteInsumo_Compra FOREIGN KEY REFERENCES dbo.Compra (Id),   -- NULL: lote de ajuste o de elaboracion
        Origen NVARCHAR(12) NOT NULL CONSTRAINT DF_LoteInsumo_Origen DEFAULT N'Compra',
        FechaIngreso DATETIME NOT NULL CONSTRAINT DF_LoteInsumo_FechaIngreso DEFAULT GETDATE(),
        FechaVencimiento DATE NULL,                         -- NULL: no vence
        TamanoPresentacion DECIMAL(12,3) NULL,              -- tamano de cada bolsa/botella en unidad base (informativo)
        CantidadPresentaciones INT NULL,                    -- cuantas bolsas/botellas entraron (informativo)
        CantidadInicial DECIMAL(12,3) NOT NULL,             -- en unidad base
        CantidadActual DECIMAL(12,3) NOT NULL,              -- lo que queda, en unidad base
        CostoUnitario DECIMAL(14,6) NOT NULL,               -- costo por unidad base (por gramo, por ml, por unidad)
        Estado NVARCHAR(10) NOT NULL CONSTRAINT DF_LoteInsumo_Estado DEFAULT N'Activo',
        CONSTRAINT CK_LoteInsumo_Origen CHECK (Origen IN (N'Compra', N'Ajuste', N'Elaboracion')),
        CONSTRAINT CK_LoteInsumo_Estado CHECK (Estado IN (N'Activo', N'Agotado', N'Vencido', N'Baja')),
        CONSTRAINT CK_LoteInsumo_CantidadInicial CHECK (CantidadInicial > 0),
        CONSTRAINT CK_LoteInsumo_CantidadActual CHECK (CantidadActual >= 0 AND CantidadActual <= CantidadInicial),
        CONSTRAINT CK_LoteInsumo_Costo CHECK (CostoUnitario >= 0)
    );
END
GO

-- Consumo FEFO: lotes activos de un insumo, el que vence antes primero (los que no vencen, al final)
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_LoteInsumo_FEFO' AND object_id = OBJECT_ID('dbo.LoteInsumo')
)
    CREATE INDEX IX_LoteInsumo_FEFO ON dbo.LoteInsumo (IdInsumo, FechaVencimiento, FechaIngreso, Id)
        INCLUDE (CantidadActual) WHERE Estado = N'Activo';
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_LoteInsumo_Compra' AND object_id = OBJECT_ID('dbo.LoteInsumo')
)
    CREATE INDEX IX_LoteInsumo_Compra ON dbo.LoteInsumo (IdCompra) WHERE IdCompra IS NOT NULL;
GO

-- ---------- MovimientoStock (libro de movimientos) ----------
-- Cada cambio en la cantidad de un lote es una fila; nunca se edita ni se borra (un error se corrige con otro movimiento).
-- Cantidad con signo: positiva entra, negativa sale.
--   Compra / Elaboracion : entran (positiva)       Consumo / Perdida / Vencido : salen (negativa)
--   Ajuste (inventario)  : cualquier signo         Devolucion (de cliente o a proveedor): cualquier signo
IF OBJECT_ID('dbo.MovimientoStock', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MovimientoStock (
        Id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MovimientoStock PRIMARY KEY,
        IdLote INT NOT NULL CONSTRAINT FK_MovimientoStock_Lote FOREIGN KEY REFERENCES dbo.LoteInsumo (Id),
        Tipo NVARCHAR(12) NOT NULL,
        Cantidad DECIMAL(12,3) NOT NULL,
        FechaHora DATETIME NOT NULL CONSTRAINT DF_MovimientoStock_FechaHora DEFAULT GETDATE(),
        IdEmpleado INT NULL CONSTRAINT FK_MovimientoStock_Empleado FOREIGN KEY REFERENCES dbo.Empleado (Id),   -- NULL: lo hizo el sistema (consumo, vencimiento)
        IdJornada INT NULL CONSTRAINT FK_MovimientoStock_Jornada FOREIGN KEY REFERENCES dbo.Jornada (Id),
        IdComandaRecibida INT NULL CONSTRAINT FK_MovimientoStock_Comanda FOREIGN KEY REFERENCES dbo.ComandaRecibida (Id),   -- consumo que origino una comanda
        Motivo NVARCHAR(100) NULL,
        Nota NVARCHAR(300) NULL,
        CONSTRAINT CK_MovimientoStock_Tipo CHECK (Tipo IN
            (N'Compra', N'Consumo', N'Perdida', N'Ajuste', N'Devolucion', N'Vencido', N'Elaboracion')),
        CONSTRAINT CK_MovimientoStock_Cantidad CHECK (Cantidad <> 0),
        CONSTRAINT CK_MovimientoStock_Signo CHECK (
            (Tipo IN (N'Compra', N'Elaboracion') AND Cantidad > 0)
            OR (Tipo IN (N'Consumo', N'Perdida', N'Vencido') AND Cantidad < 0)
            OR Tipo IN (N'Ajuste', N'Devolucion')
        )
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_MovimientoStock_Lote' AND object_id = OBJECT_ID('dbo.MovimientoStock')
)
    CREATE INDEX IX_MovimientoStock_Lote ON dbo.MovimientoStock (IdLote);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_MovimientoStock_FechaHora' AND object_id = OBJECT_ID('dbo.MovimientoStock')
)
    CREATE INDEX IX_MovimientoStock_FechaHora ON dbo.MovimientoStock (FechaHora);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_MovimientoStock_Comanda' AND object_id = OBJECT_ID('dbo.MovimientoStock')
)
    CREATE INDEX IX_MovimientoStock_Comanda ON dbo.MovimientoStock (IdComandaRecibida) WHERE IdComandaRecibida IS NOT NULL;
GO

-- ---------- vw_StockInsumo ----------
-- Stock actual de cada insumo (suma de sus lotes activos), porcentaje del objetivo y semaforo.
-- Estado: Agotado (sin stock) / SinObjetivo (no se definio el 100%) / Critico (rojo) / Bajo (amarillo) / Ok (verde).
-- Los lotes vencidos siguen contando hasta que se les da de baja (al comenzar la jornada, o con el boton manual).
CREATE OR ALTER VIEW dbo.vw_StockInsumo
AS
SELECT
    i.Id AS IdInsumo,
    i.Nombre,
    i.TipoMedida,
    i.StockObjetivo,
    i.UmbralBajoPct,
    i.UmbralCriticoPct,
    i.Activo,
    x.StockActual,
    p.Porcentaje,
    CASE
        WHEN x.StockActual <= 0 THEN N'Agotado'
        WHEN p.Porcentaje IS NULL THEN N'SinObjetivo'
        WHEN p.Porcentaje <= i.UmbralCriticoPct THEN N'Critico'
        WHEN p.Porcentaje <= i.UmbralBajoPct THEN N'Bajo'
        ELSE N'Ok'
    END AS Estado
FROM dbo.Insumo AS i
CROSS APPLY (
    SELECT CAST(ISNULL(SUM(l.CantidadActual), 0) AS DECIMAL(14,3)) AS StockActual
    FROM dbo.LoteInsumo AS l
    WHERE l.IdInsumo = i.Id AND l.Estado = N'Activo'
) AS x
CROSS APPLY (
    SELECT CASE WHEN i.StockObjetivo > 0
                THEN CAST(ROUND(x.StockActual * 100.0 / i.StockObjetivo, 1) AS DECIMAL(7,1))
           END AS Porcentaje
) AS p;
GO
