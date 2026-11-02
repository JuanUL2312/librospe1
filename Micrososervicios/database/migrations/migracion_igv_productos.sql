-- IGV por producto. El precio existente es el precio final al cliente.
-- En productos gravados, la tasa conjunta IGV + IPM se desglosa del precio.
-- Los productos exonerados deben clasificarse expresamente en el catálogo.

ALTER TABLE `librospe_ms_inventario`.`inventario_productos`
  ADD COLUMN IF NOT EXISTS `igv_tipo` VARCHAR(12) NOT NULL DEFAULT 'gravado';

ALTER TABLE `librospe_ms_ventas`.`ventas`
  ADD COLUMN IF NOT EXISTS `precio_unitario` DECIMAL(10,2) NULL,
  ADD COLUMN IF NOT EXISTS `igv_tipo` VARCHAR(12) NULL,
  ADD COLUMN IF NOT EXISTS `igv_base` DECIMAL(10,2) NULL,
  ADD COLUMN IF NOT EXISTS `igv_monto` DECIMAL(10,2) NULL,
  ADD COLUMN IF NOT EXISTS `ipm_monto` DECIMAL(10,2) NULL;

ALTER TABLE `librospe_ms_inventario`.`ventas`
  ADD COLUMN IF NOT EXISTS `precio_unitario` DECIMAL(10,2) NULL,
  ADD COLUMN IF NOT EXISTS `igv_tipo` VARCHAR(12) NULL,
  ADD COLUMN IF NOT EXISTS `igv_base` DECIMAL(10,2) NULL,
  ADD COLUMN IF NOT EXISTS `igv_monto` DECIMAL(10,2) NULL,
  ADD COLUMN IF NOT EXISTS `ipm_monto` DECIMAL(10,2) NULL;

ALTER TABLE `librospe_ms_ventas`.`detalle_pedido`
  ADD COLUMN IF NOT EXISTS `igv_tipo` VARCHAR(12) NULL,
  ADD COLUMN IF NOT EXISTS `igv_base` DECIMAL(10,2) NULL,
  ADD COLUMN IF NOT EXISTS `igv_monto` DECIMAL(10,2) NULL,
  ADD COLUMN IF NOT EXISTS `ipm_monto` DECIMAL(10,2) NULL;

CREATE OR REPLACE VIEW `librospe_ms_ventas`.`productos` AS
SELECT `id`, `nombre`, `descripcion`, `cantidad`, `proveedor_id`, `precio`, `imagen`,
       `id_categoria`, `precio_oferta`, `destacado`, `codigo_barras`, `estado`,
       `stock_minimo`, `stock_maximo`, `costo`, `igv_tipo`
FROM `librospe_ms_inventario`.`inventario_productos`;
