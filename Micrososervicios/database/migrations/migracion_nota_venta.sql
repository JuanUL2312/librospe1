-- ============================================================
-- MIGRACIÓN: NOTA DE VENTA + CONTACTO DEL CLIENTE (WhatsApp)
-- Idempotente: se puede ejecutar varias veces sin romper nada.
-- Base: librospe_db (todo calificado, se puede ejecutar con cualquier base seleccionada)
-- Ejecutar en: mysql-librospe.alwaysdata.net
--   1) Base principal: librospe_db
--   2) Microservicio de ventas: librospe_ms_ventas
-- Uso en phpMyAdmin: seleccionar la base y ejecutar este archivo.
-- ============================================================

-- ------------------------------------------------------------
-- 1) COLUMNA: tipo de comprobante acepta 'nota'
--    (nota | boleta | factura)
-- ------------------------------------------------------------
ALTER TABLE librospe_db.ventas
  MODIFY COLUMN tipo_comprobante VARCHAR(20) NOT NULL DEFAULT 'boleta';

ALTER TABLE librospe_db.ventas
  MODIFY COLUMN numero_comprobante VARCHAR(50) NULL DEFAULT NULL;

ALTER TABLE librospe_ms_ventas.comercial_ventas
  MODIFY COLUMN tipo_comprobante VARCHAR(20) NOT NULL DEFAULT 'boleta';

ALTER TABLE librospe_ms_ventas.comercial_ventas
  MODIFY COLUMN numero_comprobante VARCHAR(50) NULL DEFAULT NULL;

-- ------------------------------------------------------------
-- 2) CONTACTO DEL CLIENTE: celular para enviar el comprobante
--    por WhatsApp cuando no tiene correo
-- ------------------------------------------------------------
ALTER TABLE librospe_db.clientes
  MODIFY COLUMN telefono VARCHAR(15) NULL DEFAULT NULL;

ALTER TABLE librospe_ms_clientes.clientes
  MODIFY COLUMN telefono VARCHAR(15) NULL DEFAULT NULL;

-- ------------------------------------------------------------
-- 3) VERIFICACIÓN
-- ------------------------------------------------------------
SELECT TABLE_SCHEMA, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
FROM information_schema.COLUMNS
WHERE (TABLE_SCHEMA = 'librospe_db' AND TABLE_NAME = 'ventas'
       AND COLUMN_NAME IN ('tipo_comprobante', 'numero_comprobante'))
   OR (TABLE_SCHEMA = 'librospe_ms_ventas' AND TABLE_NAME = 'comercial_ventas'
       AND COLUMN_NAME IN ('tipo_comprobante', 'numero_comprobante'))
   OR (TABLE_SCHEMA = 'librospe_db' AND TABLE_NAME = 'clientes'
       AND COLUMN_NAME = 'telefono')
   OR (TABLE_SCHEMA = 'librospe_ms_clientes' AND TABLE_NAME = 'clientes'
       AND COLUMN_NAME = 'telefono')
ORDER BY TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME;

-- Recuento por tipo de comprobante (la fila 'nota' aparecerá
-- después de la primera venta con Nota de venta)
SELECT tipo_comprobante, COUNT(*) AS total
FROM librospe_db.ventas
GROUP BY tipo_comprobante;
