-- =============================================================
-- Reservas de stock del checkout (idempotencia + compensacion)
-- =============================================================
-- Una fila por (referencia, producto). La clave unica es la que impide
-- que un reintento del mismo pedido descuente dos veces. La tabla la crea
-- tambien el codigo de forma perezosa (CREATE TABLE IF NOT EXISTS), pero
-- este script deja la migracion explicita para produccion.
--
-- Estados:
--   reservado  -> stock descontado, pedido aun no confirmado
--   confirmado -> pedido guardado y vinculado en documento_id
--   liberado   -> pedido fallido; el stock fue devuelto
--
-- Conciliacion de reservas huerfanas (proceso caido entre la reserva y el
-- pedido) transcurridos 30 minutos:
--   UPDATE librospe_ms_inventario.reservas_stock r
--     JOIN librospe_ms_inventario.inventario_productos p ON p.id = r.producto_id
--      SET p.cantidad = p.cantidad + r.cantidad,
--          r.estado = 'liberado'
--    WHERE r.estado = 'reservado'
--      AND r.creado_en < NOW() - INTERVAL 30 MINUTE;
-- (Ejecutar dentro de una transaccion y revisar antes las filas afectadas.)
-- =============================================================

CREATE TABLE IF NOT EXISTS `librospe_ms_inventario`.`reservas_stock` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `referencia` VARCHAR(64) NOT NULL,
    `producto_id` INT NOT NULL,
    `cantidad` INT NOT NULL,
    `estado` VARCHAR(16) NOT NULL DEFAULT 'reservado',
    `documento_tipo` VARCHAR(16) NULL,
    `documento_id` INT NULL,
    `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_reserva_producto` (`referencia`, `producto_id`),
    KEY `idx_reserva_estado` (`estado`),
    KEY `idx_reserva_documento` (`documento_tipo`, `documento_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
