-- Ejecutar después de verificar que librospe_ms_ventas.productos no existe.
-- Crea una vista de solo lectura; los datos viven únicamente en
-- librospe_ms_inventario.inventario_productos.
CREATE OR REPLACE VIEW librospe_ms_ventas.productos AS
SELECT id, nombre, descripcion, cantidad, proveedor_id, precio, imagen,
       id_categoria, precio_oferta, destacado, codigo_barras, estado,
       stock_minimo, stock_maximo, costo, igv_tipo
FROM librospe_ms_inventario.inventario_productos;
