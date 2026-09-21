-- =============================================
-- SINCRONIZACIÓN COMPLETA DE MICROSERVICIOS
-- =============================================

USE librospe_db;

-- =============================================
-- 1. SINCRONIZAR PEDIDOS NUEVOS
-- =============================================

-- Insertar pedidos nuevos
INSERT INTO comercial_pedidos 
    (id, cliente_id, fecha_pedido, estado, total, direccion_entrega, tipo_entrega, nota)
SELECT 
    p.id, p.cliente_id, p.fecha_pedido, p.estado, p.total, 
    p.direccion_entrega, p.tipo_entrega, p.nota
FROM pedidos p
LEFT JOIN comercial_pedidos cp ON p.id = cp.id
WHERE cp.id IS NULL;

-- Insertar detalles de pedidos nuevos
INSERT INTO comercial_detalle_pedido 
    (id, pedido_id, producto_id, cantidad, precio_unitario, subtotal)
SELECT 
    dp.id, dp.pedido_id, dp.producto_id, dp.cantidad, 
    dp.precio_unitario, dp.subtotal
FROM detalle_pedido dp
LEFT JOIN comercial_detalle_pedido cdp ON dp.id = cdp.id
WHERE cdp.id IS NULL;

-- =============================================
-- 2. ACTUALIZAR ESTADOS DE PEDIDOS EXISTENTES
-- =============================================

UPDATE comercial_pedidos cp
JOIN pedidos p ON cp.id = p.id
SET 
    cp.estado = p.estado,
    cp.total = p.total,
    cp.direccion_entrega = p.direccion_entrega
WHERE cp.estado != p.estado OR cp.total != p.total;

-- =============================================
-- 3. SINCRONIZAR STOCK (Inventario)
-- =============================================

-- Insertar productos nuevos
INSERT INTO inventario_productos 
    (id, nombre, descripcion, cantidad, proveedor_id, precio, imagen, id_categoria, precio_oferta, destacado, codigo_barras)
SELECT 
    p.id, p.nombre, p.descripcion, p.cantidad, p.proveedor_id, 
    p.precio, p.imagen, p.id_categoria, p.precio_oferta, p.destacado, p.codigo_barras
FROM productos p
LEFT JOIN inventario_productos ip ON p.id = ip.id
WHERE ip.id IS NULL;

-- Actualizar productos existentes
UPDATE inventario_productos ip
JOIN productos p ON ip.id = p.id
SET 
    ip.nombre = p.nombre,
    ip.descripcion = p.descripcion,
    ip.cantidad = p.cantidad,
    ip.proveedor_id = p.proveedor_id,
    ip.precio = p.precio,
    ip.imagen = p.imagen,
    ip.id_categoria = p.id_categoria,
    ip.precio_oferta = p.precio_oferta,
    ip.destacado = p.destacado,
    ip.codigo_barras = p.codigo_barras
WHERE ip.id = p.id;

-- =============================================
-- 4. SINCRONIZAR PROVEEDORES (Inventario) - CORREGIDO
-- =============================================

-- NOTA: proveedores NO tiene campo 'empresa'
-- Usamos el campo 'nombre' como valor para 'empresa' en inventario_proveedores

-- Insertar proveedores nuevos
INSERT INTO inventario_proveedores 
    (id, nombre, email, contacto, empresa, ruc_empresa_id)
SELECT 
    pr.id, pr.nombre, pr.email, pr.contacto, pr.nombre, pr.ruc_empresa_id
FROM proveedores pr
LEFT JOIN inventario_proveedores ipr ON pr.id = ipr.id
WHERE ipr.id IS NULL;

-- Actualizar proveedores existentes
UPDATE inventario_proveedores ipr
JOIN proveedores pr ON ipr.id = pr.id
SET 
    ipr.nombre = pr.nombre,
    ipr.email = pr.email,
    ipr.contacto = pr.contacto,
    ipr.empresa = pr.nombre,
    ipr.ruc_empresa_id = pr.ruc_empresa_id
WHERE ipr.id = pr.id;

-- =============================================
-- 5. VERIFICACIÓN FINAL
-- =============================================

SELECT 
    'PEDIDOS' AS concepto,
    (SELECT COUNT(*) FROM pedidos) AS total,
    (SELECT COUNT(*) FROM comercial_pedidos) AS sincronizados,
    ((SELECT COUNT(*) FROM pedidos) - (SELECT COUNT(*) FROM comercial_pedidos)) AS pendientes
UNION ALL
SELECT 
    'DETALLES',
    (SELECT COUNT(*) FROM detalle_pedido),
    (SELECT COUNT(*) FROM comercial_detalle_pedido),
    ((SELECT COUNT(*) FROM detalle_pedido) - (SELECT COUNT(*) FROM comercial_detalle_pedido))
UNION ALL
SELECT 
    'PRODUCTOS',
    (SELECT COUNT(*) FROM productos),
    (SELECT COUNT(*) FROM inventario_productos),
    ((SELECT COUNT(*) FROM productos) - (SELECT COUNT(*) FROM inventario_productos))
UNION ALL
SELECT 
    'PROVEEDORES',
    (SELECT COUNT(*) FROM proveedores),
    (SELECT COUNT(*) FROM inventario_proveedores),
    ((SELECT COUNT(*) FROM proveedores) - (SELECT COUNT(*) FROM inventario_proveedores));