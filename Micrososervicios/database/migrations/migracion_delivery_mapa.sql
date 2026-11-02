-- =====================================================================
--  MIGRACIÓN: COORDENADAS PARA EL MAPA DE DELIVERY
--  Idempotente: se puede ejecutar varias veces sin romper nada.
--  Base: librospe_db
--  Uso en phpMyAdmin: seleccionar librospe_db y ejecutar este archivo.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Coordenadas del punto de entrega
--    Se llenan al crear el pedido. Si el geocodificado falla quedan en
--    NULL y el administrador las coloca a mano desde /delivery/mapa
--    (botón "Ubicar en el mapa"). Por eso son NULL y no NOT NULL.
--
--    geo_precision deja honesto el punto:
--      'exacta'     = la dirección completa se resolvió
--      'aproximada' = cayó al centroide del distrito (la calle no existe
--                     en OpenStreetMap, común en Perú)
--      'manual'     = lo fijó el administrador a mano
-- ---------------------------------------------------------------------
SET @existe := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'librospe_db'
    AND TABLE_NAME   = 'pedidos'
    AND COLUMN_NAME  = 'lat'
);

SET @sql := IF(@existe = 0,
  'ALTER TABLE librospe_db.pedidos
     ADD COLUMN lat DECIMAL(10,7) NULL DEFAULT NULL COMMENT ''Latitud (WGS84)''',
  'DO 0');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @existe := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'librospe_db'
    AND TABLE_NAME   = 'pedidos'
    AND COLUMN_NAME  = 'lng'
);

SET @sql := IF(@existe = 0,
  'ALTER TABLE librospe_db.pedidos
     ADD COLUMN lng DECIMAL(10,7) NULL DEFAULT NULL COMMENT ''Longitud (WGS84)''',
  'DO 0');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @existe := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = 'librospe_db'
    AND TABLE_NAME   = 'pedidos'
    AND COLUMN_NAME  = 'geo_precision'
);

SET @sql := IF(@existe = 0,
  'ALTER TABLE librospe_db.pedidos
     ADD COLUMN geo_precision VARCHAR(10) NULL DEFAULT NULL
     COMMENT ''exacta | aproximada | manual''',
  'DO 0');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------
-- 2. Índice para no escanear toda la tabla al pintar el mapa.
--    Solo sobre pedidos de delivery: es una fracción del total.
-- ---------------------------------------------------------------------
SET @existe := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = 'librospe_db'
    AND TABLE_NAME   = 'pedidos'
    AND INDEX_NAME   = 'idx_pedidos_entrega_geo'
);

SET @sql := IF(@existe = 0,
  'ALTER TABLE librospe_db.pedidos
     ADD INDEX idx_pedidos_entrega_geo (tipo_entrega, lat, lng)',
  'DO 0');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------
-- 3. Verificación
-- ---------------------------------------------------------------------
DESCRIBE librospe_db.pedidos;

SELECT tipo_entrega,
       COUNT(*) AS pedidos,
       SUM(CASE WHEN lat IS NOT NULL AND lng IS NOT NULL THEN 1 ELSE 0 END) AS con_coordenadas
FROM librospe_db.pedidos
GROUP BY tipo_entrega;

-- =====================================================================
--  NOTA SOBRE LA SINCRONIZACIÓN
--  sincronizar.sql copia pedidos hacia librospe_ms_ventas.comercial_pedidos
--  con una lista EXPLÍCITA de columnas, así que lat/lng no rompen el cron.
--  Las coordenadas no se copian al microservicio: solo las usa el panel.
-- =====================================================================
