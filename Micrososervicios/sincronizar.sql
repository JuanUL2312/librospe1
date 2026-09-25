-- =============================================
-- SINCRONIZACIÓN COMPLETA DE MICROSERVICIOS
-- Se puede ejecutar con cualquier BD seleccionada: todo va con nombre calificado.
-- =============================================

USE librospe_db;

-- =============================================
-- 6. SINCRONIZAR A LAS BDS DE MICROSERVICIOS (principal -> MS)
-- =============================================
-- Direccion unica de la verdad: librospe_db -> librospe_ms_*.
-- Las secciones 1-5 (arriba) mantienen los espejos internos de la
-- principal que lee el dashboard; estas secciones mantienen las
-- BDs propias de cada microservicio (verificar_microservicios.sql).
-- Todo con nombres calificados: ante cualquier error el script se
-- detiene (mysql batch) y el cron lo reporta en el log.
-- Los UPDATE usan <=> (comparacion null-safe) para no perder
-- cambios de valores NULL. Las columnas de identidad unica
-- (correos, ruc, nombre de permiso) no se actualizan: si cambian
-- en la principal, la fila queda en "pendientes" como alerta.

-- =============================================
-- 6.1 VENTAS: pedidos, detalles, ventas, detalle_pedidos, cupones, cajas
-- =============================================

-- Pedidos nuevos
INSERT IGNORE INTO librospe_ms_ventas.comercial_pedidos
    (id, cliente_id, fecha_pedido, estado, total, direccion_entrega, tipo_entrega, nota,
     nombre_recibe, dni_recibe, fecha_entrega, confirmado_por, cliente_confirmo,
     fecha_confirmacion_cliente, subtotal, descuento, costo_envio, metodo_pago,
     codigo_operacion, referencia_entrega)
SELECT p.id, p.cliente_id, p.fecha_pedido, p.estado, p.total,
       p.direccion_entrega, p.tipo_entrega, p.nota,
       p.nombre_recibe, p.dni_recibe, p.fecha_entrega, p.confirmado_por, p.cliente_confirmo,
       p.fecha_confirmacion_cliente, p.subtotal, p.descuento, p.costo_envio, p.metodo_pago,
       p.codigo_operacion, p.referencia_entrega
FROM librospe_db.pedidos p
LEFT JOIN librospe_ms_ventas.comercial_pedidos cp ON cp.id = p.id
WHERE cp.id IS NULL;

-- Pedidos existentes (entrega, confirmacion, pago, totales)
UPDATE librospe_ms_ventas.comercial_pedidos cp
JOIN librospe_db.pedidos p ON cp.id = p.id
SET cp.cliente_id = p.cliente_id,
    cp.fecha_pedido = p.fecha_pedido,
    cp.estado = p.estado,
    cp.total = p.total,
    cp.direccion_entrega = p.direccion_entrega,
    cp.tipo_entrega = p.tipo_entrega,
    cp.nota = p.nota,
    cp.nombre_recibe = p.nombre_recibe,
    cp.dni_recibe = p.dni_recibe,
    cp.fecha_entrega = p.fecha_entrega,
    cp.confirmado_por = p.confirmado_por,
    cp.cliente_confirmo = p.cliente_confirmo,
    cp.fecha_confirmacion_cliente = p.fecha_confirmacion_cliente,
    cp.subtotal = p.subtotal,
    cp.descuento = p.descuento,
    cp.costo_envio = p.costo_envio,
    cp.metodo_pago = p.metodo_pago,
    cp.codigo_operacion = p.codigo_operacion,
    cp.referencia_entrega = p.referencia_entrega
WHERE NOT (
    cp.cliente_id <=> p.cliente_id AND
    cp.fecha_pedido <=> p.fecha_pedido AND
    cp.estado <=> p.estado AND
    cp.total <=> p.total AND
    cp.direccion_entrega <=> p.direccion_entrega AND
    cp.tipo_entrega <=> p.tipo_entrega AND
    cp.nota <=> p.nota AND
    cp.nombre_recibe <=> p.nombre_recibe AND
    cp.dni_recibe <=> p.dni_recibe AND
    cp.fecha_entrega <=> p.fecha_entrega AND
    cp.confirmado_por <=> p.confirmado_por AND
    cp.cliente_confirmo <=> p.cliente_confirmo AND
    cp.fecha_confirmacion_cliente <=> p.fecha_confirmacion_cliente AND
    cp.subtotal <=> p.subtotal AND
    cp.descuento <=> p.descuento AND
    cp.costo_envio <=> p.costo_envio AND
    cp.metodo_pago <=> p.metodo_pago AND
    cp.codigo_operacion <=> p.codigo_operacion AND
    cp.referencia_entrega <=> p.referencia_entrega
);

-- Detalles (detalle_pedido singular) nuevos
INSERT IGNORE INTO librospe_ms_ventas.comercial_detalle_pedido
    (id, pedido_id, producto_id, cantidad, precio_unitario, subtotal)
SELECT dp.id, dp.pedido_id, dp.producto_id, dp.cantidad,
       dp.precio_unitario, dp.subtotal
FROM librospe_db.detalle_pedido dp
LEFT JOIN librospe_ms_ventas.comercial_detalle_pedido cdp ON cdp.id = dp.id
WHERE cdp.id IS NULL;

-- Detalles existentes
UPDATE librospe_ms_ventas.comercial_detalle_pedido cdp
JOIN librospe_db.detalle_pedido dp ON cdp.id = dp.id
SET cdp.pedido_id = dp.pedido_id,
    cdp.producto_id = dp.producto_id,
    cdp.cantidad = dp.cantidad,
    cdp.precio_unitario = dp.precio_unitario,
    cdp.subtotal = dp.subtotal
WHERE NOT (
    cdp.pedido_id <=> dp.pedido_id AND
    cdp.producto_id <=> dp.producto_id AND
    cdp.cantidad <=> dp.cantidad AND
    cdp.precio_unitario <=> dp.precio_unitario AND
    cdp.subtotal <=> dp.subtotal
);

-- Ventas nuevas
INSERT IGNORE INTO librospe_ms_ventas.comercial_ventas
    (id, producto_id, fecha_venta, cantidad, vendedor_id, cliente_id,
     tipo_comprobante, numero_comprobante, estado,
     cliente_nombres, cliente_apellidos, cliente_documento, cliente_email,
     cliente_direccion, cliente_direccion_fiscal, cliente_razon_social,
     pedido_id, metodo_pago, monto_recibido, vuelto, cliente_tipo_documento)
SELECT v.id, v.producto_id, v.fecha_venta, v.cantidad, v.vendedor_id, v.cliente_id,
       v.tipo_comprobante, v.numero_comprobante, v.estado,
       v.cliente_nombres, v.cliente_apellidos, v.cliente_documento, v.cliente_email,
       v.cliente_direccion, v.cliente_direccion_fiscal, v.cliente_razon_social,
       v.pedido_id, v.metodo_pago, v.monto_recibido, v.vuelto, v.cliente_tipo_documento
FROM librospe_db.ventas v
LEFT JOIN librospe_ms_ventas.comercial_ventas cv ON cv.id = v.id
WHERE cv.id IS NULL;

-- Ventas existentes (pago, comprobante, datos del cliente)
UPDATE librospe_ms_ventas.comercial_ventas cv
JOIN librospe_db.ventas v ON cv.id = v.id
SET cv.producto_id = v.producto_id,
    cv.fecha_venta = v.fecha_venta,
    cv.cantidad = v.cantidad,
    cv.vendedor_id = v.vendedor_id,
    cv.cliente_id = v.cliente_id,
    cv.tipo_comprobante = v.tipo_comprobante,
    cv.numero_comprobante = v.numero_comprobante,
    cv.estado = v.estado,
    cv.cliente_nombres = v.cliente_nombres,
    cv.cliente_apellidos = v.cliente_apellidos,
    cv.cliente_documento = v.cliente_documento,
    cv.cliente_email = v.cliente_email,
    cv.cliente_direccion = v.cliente_direccion,
    cv.cliente_direccion_fiscal = v.cliente_direccion_fiscal,
    cv.cliente_razon_social = v.cliente_razon_social,
    cv.pedido_id = v.pedido_id,
    cv.metodo_pago = v.metodo_pago,
    cv.monto_recibido = v.monto_recibido,
    cv.vuelto = v.vuelto,
    cv.cliente_tipo_documento = v.cliente_tipo_documento
WHERE NOT (
    cv.producto_id <=> v.producto_id AND
    cv.fecha_venta <=> v.fecha_venta AND
    cv.cantidad <=> v.cantidad AND
    cv.vendedor_id <=> v.vendedor_id AND
    cv.cliente_id <=> v.cliente_id AND
    cv.tipo_comprobante <=> v.tipo_comprobante AND
    cv.numero_comprobante <=> v.numero_comprobante AND
    cv.estado <=> v.estado AND
    cv.cliente_nombres <=> v.cliente_nombres AND
    cv.cliente_apellidos <=> v.cliente_apellidos AND
    cv.cliente_documento <=> v.cliente_documento AND
    cv.cliente_email <=> v.cliente_email AND
    cv.cliente_direccion <=> v.cliente_direccion AND
    cv.cliente_direccion_fiscal <=> v.cliente_direccion_fiscal AND
    cv.cliente_razon_social <=> v.cliente_razon_social AND
    cv.pedido_id <=> v.pedido_id AND
    cv.metodo_pago <=> v.metodo_pago AND
    cv.monto_recibido <=> v.monto_recibido AND
    cv.vuelto <=> v.vuelto AND
    cv.cliente_tipo_documento <=> v.cliente_tipo_documento
);

-- detalle_pedidos (plural) nuevos
INSERT IGNORE INTO librospe_ms_ventas.detalle_pedidos
    (id, pedido_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
SELECT dp.id, dp.pedido_id, dp.producto_id, dp.nombre_producto, dp.cantidad,
       dp.precio_unitario, dp.subtotal
FROM librospe_db.detalle_pedidos dp
LEFT JOIN librospe_ms_ventas.detalle_pedidos mdp ON mdp.id = dp.id
WHERE mdp.id IS NULL;

-- detalle_pedidos existentes
UPDATE librospe_ms_ventas.detalle_pedidos mdp
JOIN librospe_db.detalle_pedidos dp ON mdp.id = dp.id
SET mdp.pedido_id = dp.pedido_id,
    mdp.producto_id = dp.producto_id,
    mdp.nombre_producto = dp.nombre_producto,
    mdp.cantidad = dp.cantidad,
    mdp.precio_unitario = dp.precio_unitario,
    mdp.subtotal = dp.subtotal
WHERE NOT (
    mdp.pedido_id <=> dp.pedido_id AND
    mdp.producto_id <=> dp.producto_id AND
    mdp.nombre_producto <=> dp.nombre_producto AND
    mdp.cantidad <=> dp.cantidad AND
    mdp.precio_unitario <=> dp.precio_unitario AND
    mdp.subtotal <=> dp.subtotal
);

-- Cupones nuevos
INSERT IGNORE INTO librospe_ms_ventas.cupones
    (id, codigo, tipo, valor, minimo_compra, usos_maximos, usos_actuales,
     fecha_expiracion, activo, fecha_creacion)
SELECT c.id, c.codigo, c.tipo, c.valor, c.minimo_compra, c.usos_maximos, c.usos_actuales,
       c.fecha_expiracion, c.activo, c.fecha_creacion
FROM librospe_db.cupones c
LEFT JOIN librospe_ms_ventas.cupones mc ON mc.id = c.id
WHERE mc.id IS NULL;

-- Cupones existentes (usos y vigencia cambian)
UPDATE librospe_ms_ventas.cupones mc
JOIN librospe_db.cupones c ON mc.id = c.id
SET mc.codigo = c.codigo,
    mc.tipo = c.tipo,
    mc.valor = c.valor,
    mc.minimo_compra = c.minimo_compra,
    mc.usos_maximos = c.usos_maximos,
    mc.usos_actuales = c.usos_actuales,
    mc.fecha_expiracion = c.fecha_expiracion,
    mc.activo = c.activo
WHERE NOT (
    mc.codigo <=> c.codigo AND
    mc.tipo <=> c.tipo AND
    mc.valor <=> c.valor AND
    mc.minimo_compra <=> c.minimo_compra AND
    mc.usos_maximos <=> c.usos_maximos AND
    mc.usos_actuales <=> c.usos_actuales AND
    mc.fecha_expiracion <=> c.fecha_expiracion AND
    mc.activo <=> c.activo
);

-- Cajas nuevas
INSERT IGNORE INTO librospe_ms_ventas.cajas
    (id, usuario_id, monto_inicial, fecha_apertura, fecha_cierre,
     monto_esperado, monto_real, diferencia, estado)
SELECT cj.id, cj.usuario_id, cj.monto_inicial, cj.fecha_apertura, cj.fecha_cierre,
       cj.monto_esperado, cj.monto_real, cj.diferencia, cj.estado
FROM librospe_db.cajas cj
LEFT JOIN librospe_ms_ventas.cajas mcj ON mcj.id = cj.id
WHERE mcj.id IS NULL;

-- Cajas existentes (el cierre actualiza la fila)
UPDATE librospe_ms_ventas.cajas mcj
JOIN librospe_db.cajas cj ON mcj.id = cj.id
SET mcj.usuario_id = cj.usuario_id,
    mcj.monto_inicial = cj.monto_inicial,
    mcj.fecha_apertura = cj.fecha_apertura,
    mcj.fecha_cierre = cj.fecha_cierre,
    mcj.monto_esperado = cj.monto_esperado,
    mcj.monto_real = cj.monto_real,
    mcj.diferencia = cj.diferencia,
    mcj.estado = cj.estado
WHERE NOT (
    mcj.usuario_id <=> cj.usuario_id AND
    mcj.monto_inicial <=> cj.monto_inicial AND
    mcj.fecha_apertura <=> cj.fecha_apertura AND
    mcj.fecha_cierre <=> cj.fecha_cierre AND
    mcj.monto_esperado <=> cj.monto_esperado AND
    mcj.monto_real <=> cj.monto_real AND
    mcj.diferencia <=> cj.diferencia AND
    mcj.estado <=> cj.estado
);

-- =============================================
-- 6.2 INVENTARIO: categorias, productos, proveedores
-- =============================================

-- Categorias nuevas
INSERT IGNORE INTO librospe_ms_inventario.inventario_categorias
    (id_categoria, nombre, descripcion, activo)
SELECT c.id_categoria, c.nombre, c.descripcion, c.activo
FROM librospe_db.categorias c
LEFT JOIN librospe_ms_inventario.inventario_categorias ic ON ic.id_categoria = c.id_categoria
WHERE ic.id_categoria IS NULL;

-- Categorias existentes
UPDATE librospe_ms_inventario.inventario_categorias ic
JOIN librospe_db.categorias c ON ic.id_categoria = c.id_categoria
SET ic.nombre = c.nombre,
    ic.descripcion = c.descripcion,
    ic.activo = c.activo
WHERE NOT (
    ic.nombre <=> c.nombre AND
    ic.descripcion <=> c.descripcion AND
    ic.activo <=> c.activo
);

-- Productos nuevos
INSERT IGNORE INTO librospe_ms_inventario.inventario_productos
    (id, nombre, descripcion, cantidad, proveedor_id, precio, imagen,
     id_categoria, precio_oferta, destacado, codigo_barras,
     estado, stock_minimo, stock_maximo, costo)
SELECT p.id, p.nombre, p.descripcion, p.cantidad, p.proveedor_id, p.precio, p.imagen,
       p.id_categoria, p.precio_oferta, p.destacado, p.codigo_barras,
       p.estado, p.stock_minimo, p.stock_maximo, p.costo
FROM librospe_db.productos p
LEFT JOIN librospe_ms_inventario.inventario_productos ip ON ip.id = p.id
WHERE ip.id IS NULL;

-- Productos existentes (precio, stock y costo cambian)
UPDATE librospe_ms_inventario.inventario_productos ip
JOIN librospe_db.productos p ON ip.id = p.id
SET ip.nombre = p.nombre,
    ip.descripcion = p.descripcion,
    ip.cantidad = p.cantidad,
    ip.proveedor_id = p.proveedor_id,
    ip.precio = p.precio,
    ip.imagen = p.imagen,
    ip.id_categoria = p.id_categoria,
    ip.precio_oferta = p.precio_oferta,
    ip.destacado = p.destacado,
    ip.codigo_barras = p.codigo_barras,
    ip.estado = p.estado,
    ip.stock_minimo = p.stock_minimo,
    ip.stock_maximo = p.stock_maximo,
    ip.costo = p.costo
WHERE NOT (
    ip.nombre <=> p.nombre AND
    ip.descripcion <=> p.descripcion AND
    ip.cantidad <=> p.cantidad AND
    ip.proveedor_id <=> p.proveedor_id AND
    ip.precio <=> p.precio AND
    ip.imagen <=> p.imagen AND
    ip.id_categoria <=> p.id_categoria AND
    ip.precio_oferta <=> p.precio_oferta AND
    ip.destacado <=> p.destacado AND
    ip.codigo_barras <=> p.codigo_barras AND
    ip.estado <=> p.estado AND
    ip.stock_minimo <=> p.stock_minimo AND
    ip.stock_maximo <=> p.stock_maximo AND
    ip.costo <=> p.costo
);

-- Proveedores nuevos (empresa = nombre: columna solo del espejo)
INSERT IGNORE INTO librospe_ms_inventario.inventario_proveedores
    (id, nombre, email, contacto, empresa, ruc_empresa_id, estado)
SELECT pr.id, pr.nombre, pr.email, pr.contacto, pr.nombre, pr.ruc_empresa_id, pr.estado
FROM librospe_db.proveedores pr
LEFT JOIN librospe_ms_inventario.inventario_proveedores ipr ON ipr.id = pr.id
WHERE ipr.id IS NULL;

-- Proveedores existentes
UPDATE librospe_ms_inventario.inventario_proveedores ipr
JOIN librospe_db.proveedores pr ON ipr.id = pr.id
SET ipr.nombre = pr.nombre,
    ipr.email = pr.email,
    ipr.contacto = pr.contacto,
    ipr.empresa = pr.nombre,
    ipr.ruc_empresa_id = pr.ruc_empresa_id,
    ipr.estado = pr.estado
WHERE NOT (
    ipr.nombre <=> pr.nombre AND
    ipr.email <=> pr.email AND
    ipr.contacto <=> pr.contacto AND
    ipr.empresa <=> pr.nombre AND
    ipr.ruc_empresa_id <=> pr.ruc_empresa_id AND
    ipr.estado <=> pr.estado
);

-- =============================================
-- 6.3 USUARIOS: sistema, roles, permisos, rol_permisos,
--      auditoria, intentos_login, bloqueos
-- =============================================

-- Usuarios nuevos
INSERT IGNORE INTO librospe_ms_usuarios.usuarios_sistema
    (id, correo, nombres, apellidos, clave, estado, rol_id, rol, documento, debe_cambiar_clave)
SELECT u.id, u.correo, u.nombres, u.apellidos, u.clave, u.estado, u.rol_id, u.rol, u.documento, u.debe_cambiar_clave
FROM librospe_db.usuarios_sistema u
LEFT JOIN librospe_ms_usuarios.usuarios_sistema mu ON mu.id = u.id
WHERE mu.id IS NULL;

-- Usuarios existentes (clave, rol y estado cambian; el correo es
-- identidad unica y no se actualiza para no abortar el cron)
UPDATE librospe_ms_usuarios.usuarios_sistema mu
JOIN librospe_db.usuarios_sistema u ON mu.id = u.id
SET mu.nombres = u.nombres,
    mu.apellidos = u.apellidos,
    mu.clave = u.clave,
    mu.estado = u.estado,
    mu.rol_id = u.rol_id,
    mu.rol = u.rol,
    mu.documento = u.documento,
    mu.debe_cambiar_clave = u.debe_cambiar_clave
WHERE NOT (
    mu.nombres <=> u.nombres AND
    mu.apellidos <=> u.apellidos AND
    mu.clave <=> u.clave AND
    mu.estado <=> u.estado AND
    mu.rol_id <=> u.rol_id AND
    mu.rol <=> u.rol AND
    mu.documento <=> u.documento AND
    mu.debe_cambiar_clave <=> u.debe_cambiar_clave
);

-- Roles nuevos
INSERT IGNORE INTO librospe_ms_usuarios.roles
    (id, nombre, descripcion, estado)
SELECT r.id, r.nombre, r.descripcion, r.estado
FROM librospe_db.roles r
LEFT JOIN librospe_ms_usuarios.roles mr ON mr.id = r.id
WHERE mr.id IS NULL;

-- Roles existentes
UPDATE librospe_ms_usuarios.roles mr
JOIN librospe_db.roles r ON mr.id = r.id
SET mr.nombre = r.nombre,
    mr.descripcion = r.descripcion,
    mr.estado = r.estado
WHERE NOT (
    mr.nombre <=> r.nombre AND
    mr.descripcion <=> r.descripcion AND
    mr.estado <=> r.estado
);

-- Permisos nuevos
INSERT IGNORE INTO librospe_ms_usuarios.permisos
    (id, nombre, descripcion)
SELECT p.id, p.nombre, p.descripcion
FROM librospe_db.permisos p
LEFT JOIN librospe_ms_usuarios.permisos mp ON mp.id = p.id
WHERE mp.id IS NULL;

-- Permisos existentes (el nombre es identidad unica: no se actualiza)
UPDATE librospe_ms_usuarios.permisos mp
JOIN librospe_db.permisos p ON mp.id = p.id
SET mp.descripcion = p.descripcion
WHERE NOT (mp.descripcion <=> p.descripcion);

-- rol_permisos nuevos (solo insercion: asignaciones inmutables)
INSERT IGNORE INTO librospe_ms_usuarios.rol_permisos
    (id, rol_id, permiso_id)
SELECT rp.id, rp.rol_id, rp.permiso_id
FROM librospe_db.rol_permisos rp
LEFT JOIN librospe_ms_usuarios.rol_permisos mrp ON mrp.id = rp.id
WHERE mrp.id IS NULL;

-- Auditoria nueva (solo insercion: bitacora inmutable)
INSERT IGNORE INTO librospe_ms_usuarios.auditoria
    (id, usuario_id, accion, modulo, detalle, fecha)
SELECT a.id, a.usuario_id, a.accion, a.modulo, a.detalle, a.fecha
FROM librospe_db.auditoria a
LEFT JOIN librospe_ms_usuarios.auditoria ma ON ma.id = a.id
WHERE ma.id IS NULL;

-- Intentos de login nuevos
INSERT IGNORE INTO librospe_ms_usuarios.intentos_login
    (id, email, cliente_id, usuario_sistema_id, ip, intentos, ultimo_intento,
     usuarios_distintos, email_bloqueado, ips_bloqueadas, intentos_totales)
SELECT s.id, s.email, s.cliente_id, s.usuario_sistema_id, s.ip, s.intentos, s.ultimo_intento,
       s.usuarios_distintos, s.email_bloqueado, s.ips_bloqueadas, s.intentos_totales
FROM librospe_db.intentos_login s
LEFT JOIN librospe_ms_usuarios.intentos_login mi ON mi.id = s.id
WHERE mi.id IS NULL;

-- Intentos existentes (los contadores se actualizan en la principal)
UPDATE librospe_ms_usuarios.intentos_login mi
JOIN librospe_db.intentos_login s ON mi.id = s.id
SET mi.email = s.email,
    mi.cliente_id = s.cliente_id,
    mi.usuario_sistema_id = s.usuario_sistema_id,
    mi.ip = s.ip,
    mi.intentos = s.intentos,
    mi.ultimo_intento = s.ultimo_intento,
    mi.usuarios_distintos = s.usuarios_distintos,
    mi.email_bloqueado = s.email_bloqueado,
    mi.ips_bloqueadas = s.ips_bloqueadas,
    mi.intentos_totales = s.intentos_totales
WHERE NOT (
    mi.email <=> s.email AND
    mi.cliente_id <=> s.cliente_id AND
    mi.usuario_sistema_id <=> s.usuario_sistema_id AND
    mi.ip <=> s.ip AND
    mi.intentos <=> s.intentos AND
    mi.ultimo_intento <=> s.ultimo_intento AND
    mi.usuarios_distintos <=> s.usuarios_distintos AND
    mi.email_bloqueado <=> s.email_bloqueado AND
    mi.ips_bloqueadas <=> s.ips_bloqueadas AND
    mi.intentos_totales <=> s.intentos_totales
);

-- Bloqueos nuevos
INSERT IGNORE INTO librospe_ms_usuarios.bloqueos
    (id, tipo_usuario, usuario_sistema_id, cliente_id, motivo, bloqueado_por,
     fecha_bloqueo, fecha_desbloqueo, desbloqueado_por, estado, permanente, minutos_bloqueo)
SELECT b.id, b.tipo_usuario, b.usuario_sistema_id, b.cliente_id, b.motivo, b.bloqueado_por,
       b.fecha_bloqueo, b.fecha_desbloqueo, b.desbloqueado_por, b.estado, b.permanente, b.minutos_bloqueo
FROM librospe_db.bloqueos b
LEFT JOIN librospe_ms_usuarios.bloqueos mb ON mb.id = b.id
WHERE mb.id IS NULL;

-- Bloqueos existentes (el desbloqueo actualiza la fila)
UPDATE librospe_ms_usuarios.bloqueos mb
JOIN librospe_db.bloqueos b ON mb.id = b.id
SET mb.tipo_usuario = b.tipo_usuario,
    mb.usuario_sistema_id = b.usuario_sistema_id,
    mb.cliente_id = b.cliente_id,
    mb.motivo = b.motivo,
    mb.bloqueado_por = b.bloqueado_por,
    mb.fecha_bloqueo = b.fecha_bloqueo,
    mb.fecha_desbloqueo = b.fecha_desbloqueo,
    mb.desbloqueado_por = b.desbloqueado_por,
    mb.estado = b.estado,
    mb.permanente = b.permanente,
    mb.minutos_bloqueo = b.minutos_bloqueo
WHERE NOT (
    mb.tipo_usuario <=> b.tipo_usuario AND
    mb.usuario_sistema_id <=> b.usuario_sistema_id AND
    mb.cliente_id <=> b.cliente_id AND
    mb.motivo <=> b.motivo AND
    mb.bloqueado_por <=> b.bloqueado_por AND
    mb.fecha_bloqueo <=> b.fecha_bloqueo AND
    mb.fecha_desbloqueo <=> b.fecha_desbloqueo AND
    mb.desbloqueado_por <=> b.desbloqueado_por AND
    mb.estado <=> b.estado AND
    mb.permanente <=> b.permanente AND
    mb.minutos_bloqueo <=> b.minutos_bloqueo
);

-- =============================================
-- 6.4 CLIENTES: registrados, ruc_empresas y ubigeo
-- =============================================

-- Clientes nuevos (aqui entra cada registro de /registro-cliente)
INSERT IGNORE INTO librospe_ms_clientes.clientes
    (id, dni, nombres, apellidos, correo, telefono, direccion, clave,
     fecha_registro, token_recuperacion, token_expiracion, puntos, estado,
     ruc, departamento, provincia, distrito, ce, referencia)
SELECT c.id, c.dni, c.nombres, c.apellidos, c.correo, c.telefono, c.direccion, c.clave,
       c.fecha_registro, c.token_recuperacion, c.token_expiracion, c.puntos, c.estado,
       c.ruc, c.departamento, c.provincia, c.distrito, c.ce, c.referencia
FROM librospe_db.clientes c
LEFT JOIN librospe_ms_clientes.clientes mc ON mc.id = c.id
WHERE mc.id IS NULL;

-- Clientes existentes (perfil, clave, puntos, ubigeo; el correo es
-- identidad unica y no se actualiza para no abortar el cron)
UPDATE librospe_ms_clientes.clientes mc
JOIN librospe_db.clientes c ON mc.id = c.id
SET mc.dni = c.dni,
    mc.nombres = c.nombres,
    mc.apellidos = c.apellidos,
    mc.telefono = c.telefono,
    mc.direccion = c.direccion,
    mc.clave = c.clave,
    mc.fecha_registro = c.fecha_registro,
    mc.token_recuperacion = c.token_recuperacion,
    mc.token_expiracion = c.token_expiracion,
    mc.puntos = c.puntos,
    mc.estado = c.estado,
    mc.ruc = c.ruc,
    mc.departamento = c.departamento,
    mc.provincia = c.provincia,
    mc.distrito = c.distrito,
    mc.ce = c.ce,
    mc.referencia = c.referencia
WHERE NOT (
    mc.dni <=> c.dni AND
    mc.nombres <=> c.nombres AND
    mc.apellidos <=> c.apellidos AND
    mc.telefono <=> c.telefono AND
    mc.direccion <=> c.direccion AND
    mc.clave <=> c.clave AND
    mc.fecha_registro <=> c.fecha_registro AND
    mc.token_recuperacion <=> c.token_recuperacion AND
    mc.token_expiracion <=> c.token_expiracion AND
    mc.puntos <=> c.puntos AND
    mc.estado <=> c.estado AND
    mc.ruc <=> c.ruc AND
    mc.departamento <=> c.departamento AND
    mc.provincia <=> c.provincia AND
    mc.distrito <=> c.distrito AND
    mc.ce <=> c.ce AND
    mc.referencia <=> c.referencia
);

-- ruc_empresas nuevas
INSERT IGNORE INTO librospe_ms_clientes.ruc_empresas
    (id, ruc, razon_social, nombre_comercial, direccion, created_at)
SELECT r.id, r.ruc, r.razon_social, r.nombre_comercial, r.direccion, r.created_at
FROM librospe_db.ruc_empresas r
LEFT JOIN librospe_ms_clientes.ruc_empresas mr ON mr.id = r.id
WHERE mr.id IS NULL;

-- ruc_empresas existentes (el ruc es identidad unica: no se actualiza)
UPDATE librospe_ms_clientes.ruc_empresas mr
JOIN librospe_db.ruc_empresas r ON mr.id = r.id
SET mr.razon_social = r.razon_social,
    mr.nombre_comercial = r.nombre_comercial,
    mr.direccion = r.direccion
WHERE NOT (
    mr.razon_social <=> r.razon_social AND
    mr.nombre_comercial <=> r.nombre_comercial AND
    mr.direccion <=> r.direccion
);

-- Ubigeo (referencia estatica; solo insercion de faltantes)
INSERT IGNORE INTO librospe_ms_clientes.departamentos
    (id, nombre, ubigeo)
SELECT d.id, d.nombre, d.ubigeo
FROM librospe_db.departamentos d
LEFT JOIN librospe_ms_clientes.departamentos md ON md.id = d.id
WHERE md.id IS NULL;

INSERT IGNORE INTO librospe_ms_clientes.provincias
    (id, nombre, ubigeo, departamento_id)
SELECT p.id, p.nombre, p.ubigeo, p.departamento_id
FROM librospe_db.provincias p
LEFT JOIN librospe_ms_clientes.provincias mp ON mp.id = p.id
WHERE mp.id IS NULL;

INSERT IGNORE INTO librospe_ms_clientes.distritos
    (id, nombre, ubigeo, provincia_id, departamento_id)
SELECT d.id, d.nombre, d.ubigeo, d.provincia_id, d.departamento_id
FROM librospe_db.distritos d
LEFT JOIN librospe_ms_clientes.distritos md ON md.id = d.id
WHERE md.id IS NULL;

-- =============================================
-- 7. VERIFICACION MS: principal vs microservicios
--    pendientes = 0 significa espejo al dia.
-- =============================================

SELECT
    'PEDIDOS_MS' AS concepto,
    (SELECT COUNT(*) FROM librospe_db.pedidos) AS total,
    (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_pedidos) AS sincronizados,
    ((SELECT COUNT(*) FROM librospe_db.pedidos) - (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_pedidos)) AS pendientes
UNION ALL
SELECT
    'DETALLE_PEDIDO_MS',
    (SELECT COUNT(*) FROM librospe_db.detalle_pedido),
    (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_detalle_pedido),
    ((SELECT COUNT(*) FROM librospe_db.detalle_pedido) - (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_detalle_pedido))
UNION ALL
SELECT
    'VENTAS_MS',
    (SELECT COUNT(*) FROM librospe_db.ventas),
    (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_ventas),
    ((SELECT COUNT(*) FROM librospe_db.ventas) - (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_ventas))
UNION ALL
SELECT
    'DETALLE_PEDIDOS_MS',
    (SELECT COUNT(*) FROM librospe_db.detalle_pedidos),
    (SELECT COUNT(*) FROM librospe_ms_ventas.detalle_pedidos),
    ((SELECT COUNT(*) FROM librospe_db.detalle_pedidos) - (SELECT COUNT(*) FROM librospe_ms_ventas.detalle_pedidos))
UNION ALL
SELECT
    'CUPONES_MS',
    (SELECT COUNT(*) FROM librospe_db.cupones),
    (SELECT COUNT(*) FROM librospe_ms_ventas.cupones),
    ((SELECT COUNT(*) FROM librospe_db.cupones) - (SELECT COUNT(*) FROM librospe_ms_ventas.cupones))
UNION ALL
SELECT
    'CAJAS_MS',
    (SELECT COUNT(*) FROM librospe_db.cajas),
    (SELECT COUNT(*) FROM librospe_ms_ventas.cajas),
    ((SELECT COUNT(*) FROM librospe_db.cajas) - (SELECT COUNT(*) FROM librospe_ms_ventas.cajas))
UNION ALL
SELECT
    'CATEGORIAS_MS',
    (SELECT COUNT(*) FROM librospe_db.categorias),
    (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_categorias),
    ((SELECT COUNT(*) FROM librospe_db.categorias) - (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_categorias))
UNION ALL
SELECT
    'PRODUCTOS_MS',
    (SELECT COUNT(*) FROM librospe_db.productos),
    (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_productos),
    ((SELECT COUNT(*) FROM librospe_db.productos) - (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_productos))
UNION ALL
SELECT
    'PROVEEDORES_MS',
    (SELECT COUNT(*) FROM librospe_db.proveedores),
    (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_proveedores),
    ((SELECT COUNT(*) FROM librospe_db.proveedores) - (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_proveedores))
UNION ALL
SELECT
    'USUARIOS_MS',
    (SELECT COUNT(*) FROM librospe_db.usuarios_sistema),
    (SELECT COUNT(*) FROM librospe_ms_usuarios.usuarios_sistema),
    ((SELECT COUNT(*) FROM librospe_db.usuarios_sistema) - (SELECT COUNT(*) FROM librospe_ms_usuarios.usuarios_sistema))
UNION ALL
SELECT
    'ROLES_MS',
    (SELECT COUNT(*) FROM librospe_db.roles),
    (SELECT COUNT(*) FROM librospe_ms_usuarios.roles),
    ((SELECT COUNT(*) FROM librospe_db.roles) - (SELECT COUNT(*) FROM librospe_ms_usuarios.roles))
UNION ALL
SELECT
    'PERMISOS_MS',
    (SELECT COUNT(*) FROM librospe_db.permisos),
    (SELECT COUNT(*) FROM librospe_ms_usuarios.permisos),
    ((SELECT COUNT(*) FROM librospe_db.permisos) - (SELECT COUNT(*) FROM librospe_ms_usuarios.permisos))
UNION ALL
SELECT
    'ROL_PERMISOS_MS',
    (SELECT COUNT(*) FROM librospe_db.rol_permisos),
    (SELECT COUNT(*) FROM librospe_ms_usuarios.rol_permisos),
    ((SELECT COUNT(*) FROM librospe_db.rol_permisos) - (SELECT COUNT(*) FROM librospe_ms_usuarios.rol_permisos))
UNION ALL
SELECT
    'AUDITORIA_MS',
    (SELECT COUNT(*) FROM librospe_db.auditoria),
    (SELECT COUNT(*) FROM librospe_ms_usuarios.auditoria),
    ((SELECT COUNT(*) FROM librospe_db.auditoria) - (SELECT COUNT(*) FROM librospe_ms_usuarios.auditoria))
UNION ALL
SELECT
    'INTENTOS_LOGIN_MS',
    (SELECT COUNT(*) FROM librospe_db.intentos_login),
    (SELECT COUNT(*) FROM librospe_ms_usuarios.intentos_login),
    ((SELECT COUNT(*) FROM librospe_db.intentos_login) - (SELECT COUNT(*) FROM librospe_ms_usuarios.intentos_login))
UNION ALL
SELECT
    'BLOQUEOS_MS',
    (SELECT COUNT(*) FROM librospe_db.bloqueos),
    (SELECT COUNT(*) FROM librospe_ms_usuarios.bloqueos),
    ((SELECT COUNT(*) FROM librospe_db.bloqueos) - (SELECT COUNT(*) FROM librospe_ms_usuarios.bloqueos))
UNION ALL
SELECT
    'CLIENTES_MS',
    (SELECT COUNT(*) FROM librospe_db.clientes),
    (SELECT COUNT(*) FROM librospe_ms_clientes.clientes),
    ((SELECT COUNT(*) FROM librospe_db.clientes) - (SELECT COUNT(*) FROM librospe_ms_clientes.clientes))
UNION ALL
SELECT
    'RUC_EMPRESAS_MS',
    (SELECT COUNT(*) FROM librospe_db.ruc_empresas),
    (SELECT COUNT(*) FROM librospe_ms_clientes.ruc_empresas),
    ((SELECT COUNT(*) FROM librospe_db.ruc_empresas) - (SELECT COUNT(*) FROM librospe_ms_clientes.ruc_empresas))
UNION ALL
SELECT
    'DEPARTAMENTOS_MS',
    (SELECT COUNT(*) FROM librospe_db.departamentos),
    (SELECT COUNT(*) FROM librospe_ms_clientes.departamentos),
    ((SELECT COUNT(*) FROM librospe_db.departamentos) - (SELECT COUNT(*) FROM librospe_ms_clientes.departamentos))
UNION ALL
SELECT
    'PROVINCIAS_MS',
    (SELECT COUNT(*) FROM librospe_db.provincias),
    (SELECT COUNT(*) FROM librospe_ms_clientes.provincias),
    ((SELECT COUNT(*) FROM librospe_db.provincias) - (SELECT COUNT(*) FROM librospe_ms_clientes.provincias))
UNION ALL
SELECT
    'DISTRITOS_MS',
    (SELECT COUNT(*) FROM librospe_db.distritos),
    (SELECT COUNT(*) FROM librospe_ms_clientes.distritos),
    ((SELECT COUNT(*) FROM librospe_db.distritos) - (SELECT COUNT(*) FROM librospe_ms_clientes.distritos));