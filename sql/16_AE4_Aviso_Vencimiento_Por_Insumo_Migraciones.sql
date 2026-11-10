USE RestauranteDB;
GO

-- Stock, hito 6.1: dias de aviso de vencimiento propios de cada insumo.
--
-- Insumo.DiasAvisoVencimiento -> con cuantos dias de anticipacion se avisa que un lote de ESTE insumo esta por vencer.
--            NULL = usa los dias generales de la tabla Configuracion (clave 'dias_aviso_vencimiento', 5 por defecto).
--            No se guarda nada en los lotes: el aviso se calcula en cada consulta con el valor actual del insumo, asi
--            que cambiarlo afecta al instante a todos sus lotes (los que ya hay y los que entren).
--
-- Es idempotente: se puede ejecutar mas de una vez.

IF COL_LENGTH('dbo.Insumo', 'DiasAvisoVencimiento') IS NULL
BEGIN
    ALTER TABLE dbo.Insumo ADD DiasAvisoVencimiento INT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = 'CK_Insumo_DiasAvisoVencimiento' AND parent_object_id = OBJECT_ID('dbo.Insumo')
)
BEGIN
    ALTER TABLE dbo.Insumo
        ADD CONSTRAINT CK_Insumo_DiasAvisoVencimiento CHECK (DiasAvisoVencimiento IS NULL OR DiasAvisoVencimiento BETWEEN 0 AND 365);
END
GO
