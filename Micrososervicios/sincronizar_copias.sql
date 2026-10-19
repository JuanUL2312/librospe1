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

-- librospe_ms_inventario.productos -> librospe_ms_ventas.productos
INSERT IGNORE INTO `librospe_ms_ventas`.`productos` (`id`, `nombre`, `descripcion`, `cantidad`, `proveedor_id`, `precio`, `imagen`, `id_categoria`, `precio_oferta`, `destacado`, `codigo_barras`, `estado`, `stock_minimo`, `stock_maximo`, `costo`)
SELECT `id`, `nombre`, `descripcion`, `cantidad`, `proveedor_id`, `precio`, `imagen`, `id_categoria`, `precio_oferta`, `destacado`, `codigo_barras`, `estado`, `stock_minimo`, `stock_maximo`, `costo` FROM `librospe_ms_inventario`.`productos`;

UPDATE `librospe_ms_ventas`.`productos` d
JOIN `librospe_ms_inventario`.`productos` s ON d.`id` = s.`id`
SET d.`nombre` = s.`nombre`, d.`descripcion` = s.`descripcion`, d.`cantidad` = s.`cantidad`, d.`proveedor_id` = s.`proveedor_id`, d.`precio` = s.`precio`, d.`imagen` = s.`imagen`, d.`id_categoria` = s.`id_categoria`, d.`precio_oferta` = s.`precio_oferta`, d.`destacado` = s.`destacado`, d.`codigo_barras` = s.`codigo_barras`, d.`estado` = s.`estado`, d.`stock_minimo` = s.`stock_minimo`, d.`stock_maximo` = s.`stock_maximo`, d.`costo` = s.`costo`;

-- librospe_ms_inventario.categorias -> librospe_ms_ventas.categorias
INSERT IGNORE INTO `librospe_ms_ventas`.`categorias` (`id_categoria`, `nombre`, `descripcion`, `activo`)
SELECT `id_categoria`, `nombre`, `descripcion`, `activo` FROM `librospe_ms_inventario`.`categorias`;

UPDATE `librospe_ms_ventas`.`categorias` d
JOIN `librospe_ms_inventario`.`categorias` s ON d.`id_categoria` = s.`id_categoria`
SET d.`nombre` = s.`nombre`, d.`descripcion` = s.`descripcion`, d.`activo` = s.`activo`;

-- librospe_ms_inventario.proveedores -> librospe_ms_ventas.proveedores
INSERT IGNORE INTO `librospe_ms_ventas`.`proveedores` (`id`, `nombre`, `email`, `contacto`, `ruc_empresa_id`, `estado`)
SELECT `id`, `nombre`, `email`, `contacto`, `ruc_empresa_id`, `estado` FROM `librospe_ms_inventario`.`proveedores`;

UPDATE `librospe_ms_ventas`.`proveedores` d
JOIN `librospe_ms_inventario`.`proveedores` s ON d.`id` = s.`id`
SET d.`nombre` = s.`nombre`, d.`email` = s.`email`, d.`contacto` = s.`contacto`, d.`ruc_empresa_id` = s.`ruc_empresa_id`, d.`estado` = s.`estado`;

-- librospe_ms_usuarios.usuarios_sistema -> librospe_ms_ventas.usuarios_sistema
INSERT IGNORE INTO `librospe_ms_ventas`.`usuarios_sistema` (`id`, `correo`, `nombres`, `apellidos`, `clave`, `estado`, `rol_id`, `rol`, `documento`, `debe_cambiar_clave`)
SELECT `id`, `correo`, `nombres`, `apellidos`, `clave`, `estado`, `rol_id`, `rol`, `documento`, `debe_cambiar_clave` FROM `librospe_ms_usuarios`.`usuarios_sistema`;

UPDATE `librospe_ms_ventas`.`usuarios_sistema` d
JOIN `librospe_ms_usuarios`.`usuarios_sistema` s ON d.`id` = s.`id`
SET d.`correo` = s.`correo`, d.`nombres` = s.`nombres`, d.`apellidos` = s.`apellidos`, d.`clave` = s.`clave`, d.`estado` = s.`estado`, d.`rol_id` = s.`rol_id`, d.`rol` = s.`rol`, d.`documento` = s.`documento`, d.`debe_cambiar_clave` = s.`debe_cambiar_clave`;

-- librospe_ms_usuarios.roles -> librospe_ms_ventas.roles
INSERT IGNORE INTO `librospe_ms_ventas`.`roles` (`id`, `nombre`, `descripcion`, `estado`)
SELECT `id`, `nombre`, `descripcion`, `estado` FROM `librospe_ms_usuarios`.`roles`;

UPDATE `librospe_ms_ventas`.`roles` d
JOIN `librospe_ms_usuarios`.`roles` s ON d.`id` = s.`id`
SET d.`nombre` = s.`nombre`, d.`descripcion` = s.`descripcion`, d.`estado` = s.`estado`;

-- librospe_ms_clientes.clientes -> librospe_ms_ventas.clientes
INSERT IGNORE INTO `librospe_ms_ventas`.`clientes` (`id`, `dni`, `nombres`, `apellidos`, `correo`, `telefono`, `direccion`, `clave`, `fecha_registro`, `estado`, `ruc`, `departamento`, `provincia`, `distrito`, `token_recuperacion`, `token_expiracion`, `puntos`, `ce`, `referencia`)
SELECT `id`, `dni`, `nombres`, `apellidos`, `correo`, `telefono`, `direccion`, `clave`, `fecha_registro`, `estado`, `ruc`, `departamento`, `provincia`, `distrito`, `token_recuperacion`, `token_expiracion`, `puntos`, `ce`, `referencia` FROM `librospe_ms_clientes`.`clientes`;

UPDATE `librospe_ms_ventas`.`clientes` d
JOIN `librospe_ms_clientes`.`clientes` s ON d.`id` = s.`id`
SET d.`dni` = s.`dni`, d.`nombres` = s.`nombres`, d.`apellidos` = s.`apellidos`, d.`correo` = s.`correo`, d.`telefono` = s.`telefono`, d.`direccion` = s.`direccion`, d.`clave` = s.`clave`, d.`fecha_registro` = s.`fecha_registro`, d.`estado` = s.`estado`, d.`ruc` = s.`ruc`, d.`departamento` = s.`departamento`, d.`provincia` = s.`provincia`, d.`distrito` = s.`distrito`, d.`token_recuperacion` = s.`token_recuperacion`, d.`token_expiracion` = s.`token_expiracion`, d.`puntos` = s.`puntos`, d.`ce` = s.`ce`, d.`referencia` = s.`referencia`;

-- librospe_ms_usuarios.usuarios_sistema -> librospe_ms_inventario.usuarios_sistema
INSERT IGNORE INTO `librospe_ms_inventario`.`usuarios_sistema` (`id`, `correo`, `nombres`, `apellidos`, `clave`, `estado`, `rol_id`, `rol`, `documento`, `debe_cambiar_clave`)
SELECT `id`, `correo`, `nombres`, `apellidos`, `clave`, `estado`, `rol_id`, `rol`, `documento`, `debe_cambiar_clave` FROM `librospe_ms_usuarios`.`usuarios_sistema`;

UPDATE `librospe_ms_inventario`.`usuarios_sistema` d
JOIN `librospe_ms_usuarios`.`usuarios_sistema` s ON d.`id` = s.`id`
SET d.`correo` = s.`correo`, d.`nombres` = s.`nombres`, d.`apellidos` = s.`apellidos`, d.`clave` = s.`clave`, d.`estado` = s.`estado`, d.`rol_id` = s.`rol_id`, d.`rol` = s.`rol`, d.`documento` = s.`documento`, d.`debe_cambiar_clave` = s.`debe_cambiar_clave`;

-- librospe_ms_ventas.ventas -> librospe_ms_inventario.ventas
INSERT IGNORE INTO `librospe_ms_inventario`.`ventas` (`id`, `producto_id`, `fecha_venta`, `cantidad`, `vendedor_id`, `cliente_id`, `tipo_comprobante`, `numero_comprobante`, `estado`, `cliente_nombres`, `cliente_apellidos`, `cliente_documento`, `cliente_email`, `cliente_direccion`, `cliente_direccion_fiscal`, `cliente_razon_social`, `pedido_id`, `metodo_pago`, `monto_recibido`, `vuelto`, `cliente_tipo_documento`, `cliente_telefono`)
SELECT `id`, `producto_id`, `fecha_venta`, `cantidad`, `vendedor_id`, `cliente_id`, `tipo_comprobante`, `numero_comprobante`, `estado`, `cliente_nombres`, `cliente_apellidos`, `cliente_documento`, `cliente_email`, `cliente_direccion`, `cliente_direccion_fiscal`, `cliente_razon_social`, `pedido_id`, `metodo_pago`, `monto_recibido`, `vuelto`, `cliente_tipo_documento`, `cliente_telefono` FROM `librospe_ms_ventas`.`ventas`;

UPDATE `librospe_ms_inventario`.`ventas` d
JOIN `librospe_ms_ventas`.`ventas` s ON d.`id` = s.`id`
SET d.`producto_id` = s.`producto_id`, d.`fecha_venta` = s.`fecha_venta`, d.`cantidad` = s.`cantidad`, d.`vendedor_id` = s.`vendedor_id`, d.`cliente_id` = s.`cliente_id`, d.`tipo_comprobante` = s.`tipo_comprobante`, d.`numero_comprobante` = s.`numero_comprobante`, d.`estado` = s.`estado`, d.`cliente_nombres` = s.`cliente_nombres`, d.`cliente_apellidos` = s.`cliente_apellidos`, d.`cliente_documento` = s.`cliente_documento`, d.`cliente_email` = s.`cliente_email`, d.`cliente_direccion` = s.`cliente_direccion`, d.`cliente_direccion_fiscal` = s.`cliente_direccion_fiscal`, d.`cliente_razon_social` = s.`cliente_razon_social`, d.`pedido_id` = s.`pedido_id`, d.`metodo_pago` = s.`metodo_pago`, d.`monto_recibido` = s.`monto_recibido`, d.`vuelto` = s.`vuelto`, d.`cliente_tipo_documento` = s.`cliente_tipo_documento`, d.`cliente_telefono` = s.`cliente_telefono`;

-- =============================================================
-- RESUMEN: filas pendientes de copiar (0 = todo en dia)
-- =============================================================
SELECT 'librospe_ms_ventas.productos' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_inventario`.`productos`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_ventas`.`productos`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_inventario`.`productos`) -
        (SELECT COUNT(*) FROM `librospe_ms_ventas`.`productos`)) AS pendientes;
SELECT 'librospe_ms_ventas.categorias' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_inventario`.`categorias`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_ventas`.`categorias`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_inventario`.`categorias`) -
        (SELECT COUNT(*) FROM `librospe_ms_ventas`.`categorias`)) AS pendientes;
SELECT 'librospe_ms_ventas.proveedores' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_inventario`.`proveedores`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_ventas`.`proveedores`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_inventario`.`proveedores`) -
        (SELECT COUNT(*) FROM `librospe_ms_ventas`.`proveedores`)) AS pendientes;
SELECT 'librospe_ms_ventas.usuarios_sistema' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_usuarios`.`usuarios_sistema`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_ventas`.`usuarios_sistema`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_usuarios`.`usuarios_sistema`) -
        (SELECT COUNT(*) FROM `librospe_ms_ventas`.`usuarios_sistema`)) AS pendientes;
SELECT 'librospe_ms_ventas.roles' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_usuarios`.`roles`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_ventas`.`roles`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_usuarios`.`roles`) -
        (SELECT COUNT(*) FROM `librospe_ms_ventas`.`roles`)) AS pendientes;
SELECT 'librospe_ms_ventas.clientes' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_clientes`.`clientes`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_ventas`.`clientes`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_clientes`.`clientes`) -
        (SELECT COUNT(*) FROM `librospe_ms_ventas`.`clientes`)) AS pendientes;
SELECT 'librospe_ms_inventario.usuarios_sistema' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_usuarios`.`usuarios_sistema`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_inventario`.`usuarios_sistema`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_usuarios`.`usuarios_sistema`) -
        (SELECT COUNT(*) FROM `librospe_ms_inventario`.`usuarios_sistema`)) AS pendientes;
SELECT 'librospe_ms_inventario.ventas' AS tabla,
       (SELECT COUNT(*) FROM `librospe_ms_ventas`.`ventas`) AS origen,
       (SELECT COUNT(*) FROM `librospe_ms_inventario`.`ventas`) AS destino,
       ((SELECT COUNT(*) FROM `librospe_ms_ventas`.`ventas`) -
        (SELECT COUNT(*) FROM `librospe_ms_inventario`.`ventas`)) AS pendientes;
