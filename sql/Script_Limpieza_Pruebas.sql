USE RestauranteDB;
GO

-- =====================================================================
-- Limpieza de datos de PRUEBA: borra las sesiones de mesa (y sus pedidos
-- y comandas) abiertas desde @Desde en adelante, y libera las mesas.
-- No toca empleados, mesas, categorias ni productos.
--
-- Uso:
--   1) Ajustar @Desde (fecha/hora en que empezaron las pruebas).
--   2) Ejecutar con @Ejecutar = 0: solo muestra QUE se borraria.
--   3) Si coincide con lo esperado, poner @Ejecutar = 1 y ejecutar de nuevo.
-- =====================================================================
DECLARE @Desde    DATETIME = '2026-10-12 00:00';
DECLARE @Ejecutar BIT      = 0;

SELECT p.Id AS Sesion, m.Numero AS Mesa, p.CodigoPin, p.CantidadComensales, p.Estado,
       p.FechaHoraApertura, p.FechaHoraCierre,
       (SELECT COUNT(*) FROM dbo.PedidoDetalle d WHERE d.IdPedidoCabecera = p.Id)   AS Detalles,
       (SELECT COUNT(*) FROM dbo.ComandaRecibida c WHERE c.IdPedidoCabecera = p.Id) AS Comandas
FROM dbo.PedidoCabecera p
JOIN dbo.Mesa m ON m.Id = p.IdMesa
WHERE p.FechaHoraApertura >= @Desde
ORDER BY p.Id;

IF @Ejecutar = 1
BEGIN
    SET XACT_ABORT ON;
    BEGIN TRANSACTION;

    DELETE d FROM dbo.PedidoDetalle d
    JOIN dbo.PedidoCabecera p ON p.Id = d.IdPedidoCabecera
    WHERE p.FechaHoraApertura >= @Desde;

    DELETE c FROM dbo.ComandaRecibida c
    JOIN dbo.PedidoCabecera p ON p.Id = c.IdPedidoCabecera
    WHERE p.FechaHoraApertura >= @Desde;

    DELETE FROM dbo.PedidoCabecera WHERE FechaHoraApertura >= @Desde;

    -- las mesas quedan libres salvo que conserven una sesion abierta anterior
    UPDATE m SET m.Estado = CASE WHEN EXISTS (
            SELECT 1 FROM dbo.PedidoCabecera p WHERE p.IdMesa = m.Id AND p.Estado = 'Abierto') THEN 1 ELSE 0 END
    FROM dbo.Mesa m;

    COMMIT TRANSACTION;
    PRINT 'Limpieza ejecutada.';
END
ELSE
    PRINT 'Modo vista previa: no se borro nada. Poner @Ejecutar = 1 para borrar.';

SELECT 'PedidoCabecera' AS Tabla, COUNT(*) AS Filas FROM dbo.PedidoCabecera
UNION ALL SELECT 'PedidoDetalle', COUNT(*) FROM dbo.PedidoDetalle
UNION ALL SELECT 'ComandaRecibida', COUNT(*) FROM dbo.ComandaRecibida
UNION ALL SELECT 'Mesas ocupadas', COUNT(*) FROM dbo.Mesa WHERE Estado = 1;
GO
