-- Idempotencia de pedidos y outbox transaccional del microservicio de ventas.
-- Ejecutar una vez contra la instalacion que use MS_VENTAS_DB=librospe_ms_ventas.
-- Las claves existentes quedan NULL y no colisionan con el indice unico.

ALTER TABLE `librospe_ms_ventas`.`pedidos`
    ADD COLUMN IF NOT EXISTS `clave_idempotencia` VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS `huella_idempotencia` VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS `stock_confirmado` TINYINT(1) NOT NULL DEFAULT 0;

UPDATE `librospe_ms_ventas`.`pedidos`
SET `stock_confirmado` = 1
WHERE `clave_idempotencia` IS NULL;

SET @indice_idem_existe := (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = 'librospe_ms_ventas'
      AND table_name = 'pedidos'
      AND index_name = 'uq_pedidos_clave_idempotencia'
);
SET @sql_indice_idem := IF(
    @indice_idem_existe = 0,
    'ALTER TABLE `librospe_ms_ventas`.`pedidos` ADD UNIQUE KEY `uq_pedidos_clave_idempotencia` (`clave_idempotencia`)',
    'SELECT 1'
);
PREPARE stmt_indice_idem FROM @sql_indice_idem;
EXECUTE stmt_indice_idem;
DEALLOCATE PREPARE stmt_indice_idem;

-- El evento pedido.creado comparte commit con pedidos/detalles/ventas.
-- mensajeria.py tambi?n puede crear esta tabla durante el despliegue inicial.
CREATE TABLE IF NOT EXISTS `librospe_ms_ventas`.`eventos_pendientes` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `tipo` VARCHAR(80) NOT NULL,
    `origen` VARCHAR(40) NULL,
    `payload` TEXT NULL,
    `estado` VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    `intentos` INT NOT NULL DEFAULT 0,
    `proximo_intento` DATETIME NULL,
    `error` TEXT NULL,
    `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `enviado_en` DATETIME NULL,
    PRIMARY KEY (`id`),
    KEY `idx_estado` (`estado`),
    KEY `idx_tipo` (`tipo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE `librospe_ms_ventas`.`eventos_pendientes`
    ADD COLUMN IF NOT EXISTS `proximo_intento` DATETIME NULL;

CREATE TABLE IF NOT EXISTS `librospe_ms_ventas`.`pos_ventas_idempotencia` (
    `clave` VARCHAR(64) NOT NULL,
    `huella` VARCHAR(64) NOT NULL,
    `referencia_stock` VARCHAR(64) NOT NULL,
    `respuesta` TEXT NOT NULL,
    `stock_confirmado` TINYINT(1) NOT NULL DEFAULT 0,
    `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`clave`),
    UNIQUE KEY `uq_pos_idem_referencia_stock` (`referencia_stock`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
