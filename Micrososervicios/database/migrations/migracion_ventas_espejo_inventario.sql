-- Restaura la copia local de ventas que el Gateway consulta en inventario.
-- No agrega claves foraneas: las entidades relacionadas pertenecen a otros
-- microservicios y esta tabla se mantiene como proyeccion de solo lectura.
CREATE TABLE IF NOT EXISTS `librospe_ms_inventario`.`ventas` (
  `id` int(11) NOT NULL,
  `producto_id` int(11) NOT NULL,
  `fecha_venta` datetime NOT NULL,
  `cantidad` int(11) NOT NULL DEFAULT 1,
  `vendedor_id` int(11) NOT NULL,
  `cliente_id` int(11) DEFAULT NULL,
  `tipo_comprobante` varchar(20) NOT NULL DEFAULT 'boleta',
  `numero_comprobante` varchar(50) DEFAULT NULL,
  `estado` tinyint(1) NOT NULL DEFAULT 1,
  `cliente_nombres` varchar(100) DEFAULT NULL,
  `cliente_apellidos` varchar(100) DEFAULT NULL,
  `cliente_documento` varchar(20) DEFAULT NULL,
  `cliente_email` varchar(150) DEFAULT NULL,
  `cliente_direccion` text DEFAULT NULL,
  `cliente_direccion_fiscal` text DEFAULT NULL,
  `cliente_razon_social` varchar(200) DEFAULT NULL,
  `pedido_id` int(11) DEFAULT NULL,
  `metodo_pago` varchar(20) DEFAULT NULL,
  `monto_recibido` decimal(10,2) DEFAULT NULL,
  `vuelto` decimal(10,2) DEFAULT NULL,
  `cliente_tipo_documento` varchar(30) DEFAULT NULL,
  `cliente_telefono` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ventas_producto_fecha` (`producto_id`, `fecha_venta`),
  KEY `idx_ventas_pedido` (`pedido_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
