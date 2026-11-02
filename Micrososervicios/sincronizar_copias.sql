-- =============================================================
-- SINCRONIZACION DE COPIAS LOCALES ENTRE MICROSERVICIOS
-- -------------------------------------------------------------
-- Cada microservicio es dueno de sus datos. Para poder hacer JOIN
-- dentro de una misma base (MySQL no une bases distintas), cada
-- servicio guarda una copia local de las claves foraneas que usa.
-- Este script mantiene esas copias al dia.
--
-- La comunicacion en tiempo real la hace el agente de mensajes
-- (RabbitMQ); este script es la red de seguridad periodica.
-- =============================================================

-- Productos no se copian: ventas lee desde la vista productos, que apunta a
-- librospe_ms_inventario.inventario_productos.

-- librospe_ms_inventario.proveedores -> librospe_ms_ventas.proveedores
INSERT IGNORE INTO `librospe_ms_ventas`.`proveedores` (`id`, `nombre`, `email`, `contacto`, `ruc_empresa_id`, `estado`)
SELECT `id`, `nombre`, `email`, `contacto`, `ruc_empresa_id`, `estado` FROM `librospe_ms_inventario`.`proveedores`;

INSERT INTO `librospe_ms_ventas`.`proveedores` (`id`, `nombre`, `email`, `contacto`, `ruc_empresa_id`, `estado`)
SELECT `id`, `nombre`, `email`, `contacto`, `ruc_empresa_id`, `estado` FROM `librospe_ms_inventario`.`proveedores`
ON DUPLICATE KEY UPDATE `nombre` = VALUES(`nombre`), `email` = VALUES(`email`), `contacto` = VALUES(`contacto`), `ruc_empresa_id` = VALUES(`ruc_empresa_id`), `estado` = VALUES(`estado`);

-- librospe_ms_ventas.ventas -> librospe_ms_inventario.ventas
INSERT IGNORE INTO `librospe_ms_inventario`.`ventas` (`id`, `producto_id`, `fecha_venta`, `cantidad`, `vendedor_id`, `precio_unitario`, `igv_tipo`, `igv_base`, `igv_monto`, `ipm_monto`, `cliente_id`, `tipo_comprobante`, `numero_comprobante`, `estado`, `cliente_nombres`, `cliente_apellidos`, `cliente_documento`, `cliente_email`, `cliente_direccion`, `cliente_direccion_fiscal`, `cliente_razon_social`, `pedido_id`, `metodo_pago`, `monto_recibido`, `vuelto`, `cliente_tipo_documento`, `cliente_telefono`)
SELECT `id`, `producto_id`, `fecha_venta`, `cantidad`, `vendedor_id`, `precio_unitario`, `igv_tipo`, `igv_base`, `igv_monto`, `ipm_monto`, `cliente_id`, `tipo_comprobante`, `numero_comprobante`, `estado`, `cliente_nombres`, `cliente_apellidos`, `cliente_documento`, `cliente_email`, `cliente_direccion`, `cliente_direccion_fiscal`, `cliente_razon_social`, `pedido_id`, `metodo_pago`, `monto_recibido`, `vuelto`, `cliente_tipo_documento`, `cliente_telefono` FROM `librospe_ms_ventas`.`ventas`;

INSERT INTO `librospe_ms_inventario`.`ventas` (`id`, `producto_id`, `fecha_venta`, `cantidad`, `vendedor_id`, `precio_unitario`, `igv_tipo`, `igv_base`, `igv_monto`, `ipm_monto`, `cliente_id`, `tipo_comprobante`, `numero_comprobante`, `estado`, `cliente_nombres`, `cliente_apellidos`, `cliente_documento`, `cliente_email`, `cliente_direccion`, `cliente_direccion_fiscal`, `cliente_razon_social`, `pedido_id`, `metodo_pago`, `monto_recibido`, `vuelto`, `cliente_tipo_documento`, `cliente_telefono`)
SELECT `id`, `producto_id`, `fecha_venta`, `cantidad`, `vendedor_id`, `precio_unitario`, `igv_tipo`, `igv_base`, `igv_monto`, `ipm_monto`, `cliente_id`, `tipo_comprobante`, `numero_comprobante`, `estado`, `cliente_nombres`, `cliente_apellidos`, `cliente_documento`, `cliente_email`, `cliente_direccion`, `cliente_direccion_fiscal`, `cliente_razon_social`, `pedido_id`, `metodo_pago`, `monto_recibido`, `vuelto`, `cliente_tipo_documento`, `cliente_telefono` FROM `librospe_ms_ventas`.`ventas`
ON DUPLICATE KEY UPDATE `producto_id` = VALUES(`producto_id`), `fecha_venta` = VALUES(`fecha_venta`), `cantidad` = VALUES(`cantidad`), `vendedor_id` = VALUES(`vendedor_id`), `precio_unitario` = VALUES(`precio_unitario`), `igv_tipo` = VALUES(`igv_tipo`), `igv_base` = VALUES(`igv_base`), `igv_monto` = VALUES(`igv_monto`), `ipm_monto` = VALUES(`ipm_monto`), `cliente_id` = VALUES(`cliente_id`), `tipo_comprobante` = VALUES(`tipo_comprobante`), `numero_comprobante` = VALUES(`numero_comprobante`), `estado` = VALUES(`estado`), `cliente_nombres` = VALUES(`cliente_nombres`), `cliente_apellidos` = VALUES(`cliente_apellidos`), `cliente_documento` = VALUES(`cliente_documento`), `cliente_email` = VALUES(`cliente_email`), `cliente_direccion` = VALUES(`cliente_direccion`), `cliente_direccion_fiscal` = VALUES(`cliente_direccion_fiscal`), `cliente_razon_social` = VALUES(`cliente_razon_social`), `pedido_id` = VALUES(`pedido_id`), `metodo_pago` = VALUES(`metodo_pago`), `monto_recibido` = VALUES(`monto_recibido`), `vuelto` = VALUES(`vuelto`), `cliente_tipo_documento` = VALUES(`cliente_tipo_documento`), `cliente_telefono` = VALUES(`cliente_telefono`);

-- =============================================================
-- RESUMEN: filas pendientes de copiar (0 = todo en dia)
-- =============================================================
SELECT 'librospe_ms_ventas.proveedores' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_inventario`.`proveedores`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_ventas`.`proveedores`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_inventario`.`proveedores`) -
        (SELECT COUNT(*) FROM `librospe_ms_ventas`.`proveedores`)) AS pendientes;
SELECT 'librospe_ms_inventario.ventas' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_ventas`.`ventas`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_inventario`.`ventas`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_ventas`.`ventas`) -
        (SELECT COUNT(*) FROM `librospe_ms_inventario`.`ventas`)) AS pendientes;
