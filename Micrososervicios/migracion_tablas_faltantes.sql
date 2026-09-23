-- ============================================================
-- MIGRACION FASE 1: TABLAS FALTANTES + ALINEACION DE ESPEJOS
-- Proyecto LibrosPE - Microservicios (MariaDB / phpMyAdmin)
-- ------------------------------------------------------------
-- Orden de ejecucion:
--   1) microservicios_bds.sql .... una vez (BDs + espejos base)
--   2) ESTE script ............... una vez (tablas que faltan + columnas)
--   3) sincronizar.sql ........... cada hora (rellena y actualiza datos)
--
-- Seguro e idempotente: se puede ejecutar varias veces.
-- - Solo LEE de librospe_db (origen). No la modifica.
-- - Solo ESCRIBE en librospe_ms_* (destino).
-- - No crea FOREIGN KEY en las BDs MS: los IDs se resuelven
--   por HTTP entre servicios (Fase 4), no con FK entre esquemas.
-- ============================================================

-- ============================================================
-- 0. ALINEAR ESPEJOS EXISTENTES CON LA PRINCIPAL (drift)
--    La principal agrego columnas que los espejos no tienen.
--    ALTERs idempotentes: ADD COLUMN IF NOT EXISTS (MariaDB).
-- ============================================================

-- MS_USUARIOS.roles: descripcion + estado
ALTER TABLE librospe_ms_usuarios.roles ADD COLUMN IF NOT EXISTS descripcion TEXT NULL;
ALTER TABLE librospe_ms_usuarios.roles ADD COLUMN IF NOT EXISTS estado TINYINT(1) NOT NULL DEFAULT 1;

-- MS_USUARIOS.usuarios_sistema: debe_cambiar_clave
ALTER TABLE librospe_ms_usuarios.usuarios_sistema ADD COLUMN IF NOT EXISTS debe_cambiar_clave TINYINT(1) DEFAULT 0;

-- MS_CLIENTES.clientes: tokens, puntos, ce, referencia
ALTER TABLE librospe_ms_clientes.clientes ADD COLUMN IF NOT EXISTS token_recuperacion VARCHAR(100) NULL;
ALTER TABLE librospe_ms_clientes.clientes ADD COLUMN IF NOT EXISTS token_expiracion DATETIME NULL;
ALTER TABLE librospe_ms_clientes.clientes ADD COLUMN IF NOT EXISTS puntos INT(11) DEFAULT 0;
ALTER TABLE librospe_ms_clientes.clientes ADD COLUMN IF NOT EXISTS ce VARCHAR(9) NULL;
ALTER TABLE librospe_ms_clientes.clientes ADD COLUMN IF NOT EXISTS referencia VARCHAR(200) NULL;

-- MS_INVENTARIO.inventario_productos: estado, stock_minimo, stock_maximo, costo
ALTER TABLE librospe_ms_inventario.inventario_productos ADD COLUMN IF NOT EXISTS estado TINYINT(1) NOT NULL DEFAULT 1;
ALTER TABLE librospe_ms_inventario.inventario_productos ADD COLUMN IF NOT EXISTS stock_minimo INT(11) DEFAULT 5;
ALTER TABLE librospe_ms_inventario.inventario_productos ADD COLUMN IF NOT EXISTS stock_maximo INT(11) DEFAULT 100;
ALTER TABLE librospe_ms_inventario.inventario_productos ADD COLUMN IF NOT EXISTS costo DECIMAL(10,2) NULL;

-- MS_INVENTARIO.inventario_proveedores: estado
ALTER TABLE librospe_ms_inventario.inventario_proveedores ADD COLUMN IF NOT EXISTS estado TINYINT(1) NOT NULL DEFAULT 1;

-- MS_VENTAS.comercial_pedidos: entrega, confirmacion y pago
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS nombre_recibe VARCHAR(200) NULL;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS dni_recibe VARCHAR(20) NULL;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS fecha_entrega DATETIME NULL;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS confirmado_por VARCHAR(100) NULL;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS cliente_confirmo INT(11) DEFAULT 0;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS fecha_confirmacion_cliente DATETIME NULL;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS subtotal FLOAT NULL;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS descuento FLOAT NOT NULL DEFAULT 0;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS costo_envio FLOAT NOT NULL DEFAULT 0;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(30) NULL;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS codigo_operacion VARCHAR(60) NULL;
ALTER TABLE librospe_ms_ventas.comercial_pedidos ADD COLUMN IF NOT EXISTS referencia_entrega VARCHAR(200) NULL;

-- MS_VENTAS.comercial_ventas: alinear tipo_comprobante con la principal (VARCHAR)
ALTER TABLE librospe_ms_ventas.comercial_ventas MODIFY COLUMN tipo_comprobante VARCHAR(20) NOT NULL DEFAULT 'boleta';
ALTER TABLE librospe_ms_ventas.comercial_ventas ADD COLUMN IF NOT EXISTS estado TINYINT(1) NOT NULL DEFAULT 1;
ALTER TABLE librospe_ms_ventas.comercial_ventas ADD COLUMN IF NOT EXISTS pedido_id INT(11) NULL;
ALTER TABLE librospe_ms_ventas.comercial_ventas ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(20) NULL;
ALTER TABLE librospe_ms_ventas.comercial_ventas ADD COLUMN IF NOT EXISTS monto_recibido DECIMAL(10,2) NULL;
ALTER TABLE librospe_ms_ventas.comercial_ventas ADD COLUMN IF NOT EXISTS vuelto DECIMAL(10,2) NULL;
ALTER TABLE librospe_ms_ventas.comercial_ventas ADD COLUMN IF NOT EXISTS cliente_tipo_documento VARCHAR(30) NULL;

-- ============================================================
-- 1. MS_CLIENTES: ruc_empresas + ubigeo (sin FK, solo IDs)
-- ============================================================
CREATE TABLE IF NOT EXISTS librospe_ms_clientes.ruc_empresas (
    id INT(11) NOT NULL AUTO_INCREMENT,
    ruc VARCHAR(11) NOT NULL,
    razon_social VARCHAR(200) NOT NULL,
    nombre_comercial VARCHAR(150) NULL,
    direccion TEXT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ruc_empresas_ruc (ruc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS librospe_ms_clientes.departamentos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    ubigeo VARCHAR(2) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS librospe_ms_clientes.provincias (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    ubigeo VARCHAR(4) NULL,
    departamento_id INT(11) NULL,
    PRIMARY KEY (id),
    KEY idx_provincias_departamento (departamento_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS librospe_ms_clientes.distritos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(150) NOT NULL,
    ubigeo VARCHAR(6) NULL,
    provincia_id INT(11) NULL,
    departamento_id INT(11) NULL,
    PRIMARY KEY (id),
    KEY idx_distritos_provincia (provincia_id),
    KEY idx_distritos_departamento (departamento_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Carga inicial desde la principal
INSERT IGNORE INTO librospe_ms_clientes.ruc_empresas
    (id, ruc, razon_social, nombre_comercial, direccion, created_at)
SELECT id, ruc, razon_social, nombre_comercial, direccion, created_at
FROM librospe_db.ruc_empresas;

INSERT IGNORE INTO librospe_ms_clientes.departamentos
    (id, nombre, ubigeo)
SELECT id, nombre, ubigeo
FROM librospe_db.departamentos;

INSERT IGNORE INTO librospe_ms_clientes.provincias
    (id, nombre, ubigeo, departamento_id)
SELECT id, nombre, ubigeo, departamento_id
FROM librospe_db.provincias;

INSERT IGNORE INTO librospe_ms_clientes.distritos
    (id, nombre, ubigeo, provincia_id, departamento_id)
SELECT id, nombre, ubigeo, provincia_id, departamento_id
FROM librospe_db.distritos;

-- ============================================================
-- 2. MS_USUARIOS: permisos, rol_permisos, auditoria,
--    intentos_login, bloqueos (sin FK, solo IDs)
-- NOTA: rol_permisos NO lleva UNIQUE (rol_id, permiso_id) porque
-- la principal tiene pares duplicados (seed corrido 2 veces);
-- el espejo copia fiel para que los conteos coincidan.
-- ============================================================
CREATE TABLE IF NOT EXISTS librospe_ms_usuarios.permisos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    descripcion VARCHAR(200) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_permisos_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS librospe_ms_usuarios.rol_permisos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    rol_id INT(11) NOT NULL,
    permiso_id INT(11) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_rp_rol (rol_id),
    KEY idx_rp_permiso (permiso_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS librospe_ms_usuarios.auditoria (
    id INT(11) NOT NULL AUTO_INCREMENT,
    usuario_id INT(11) NULL,
    accion VARCHAR(50) NOT NULL,
    modulo VARCHAR(50) NOT NULL,
    detalle TEXT NULL,
    fecha DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_auditoria_usuario (usuario_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS librospe_ms_usuarios.intentos_login (
    id INT(11) NOT NULL AUTO_INCREMENT,
    email VARCHAR(150) NULL,
    cliente_id INT(11) NULL,
    usuario_sistema_id INT(11) NULL,
    ip VARCHAR(45) NULL,
    intentos INT(11) DEFAULT 1,
    ultimo_intento DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
    usuarios_distintos INT(11) DEFAULT 0,
    email_bloqueado DATETIME NULL,
    ips_bloqueadas DATETIME NULL,
    intentos_totales INT(11) DEFAULT 0,
    PRIMARY KEY (id),
    KEY idx_intentos_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS librospe_ms_usuarios.bloqueos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    tipo_usuario ENUM('sistema','cliente') NOT NULL,
    usuario_sistema_id INT(11) NULL,
    cliente_id INT(11) NULL,
    motivo VARCHAR(255) NULL,
    bloqueado_por INT(11) NULL,
    fecha_bloqueo DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_desbloqueo DATETIME NULL,
    desbloqueado_por INT(11) NULL,
    estado TINYINT(1) NOT NULL DEFAULT 1,
    permanente TINYINT(1) DEFAULT 0,
    minutos_bloqueo INT(11) NULL,
    PRIMARY KEY (id),
    KEY idx_bloqueos_usuario (usuario_sistema_id),
    KEY idx_bloqueos_cliente (cliente_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- La principal tiene bloqueos en utf8mb4_unicode_ci (unica tabla asi);
-- el espejo debe igualarla o el sync falla con #1267 en las comparaciones.
ALTER TABLE librospe_ms_usuarios.bloqueos CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Carga inicial desde la principal
INSERT IGNORE INTO librospe_ms_usuarios.permisos
    (id, nombre, descripcion)
SELECT id, nombre, descripcion
FROM librospe_db.permisos;

INSERT IGNORE INTO librospe_ms_usuarios.rol_permisos
    (id, rol_id, permiso_id)
SELECT id, rol_id, permiso_id
FROM librospe_db.rol_permisos;

INSERT IGNORE INTO librospe_ms_usuarios.auditoria
    (id, usuario_id, accion, modulo, detalle, fecha)
SELECT id, usuario_id, accion, modulo, detalle, fecha
FROM librospe_db.auditoria;

INSERT IGNORE INTO librospe_ms_usuarios.intentos_login
    (id, email, cliente_id, usuario_sistema_id, ip, intentos, ultimo_intento,
     usuarios_distintos, email_bloqueado, ips_bloqueadas, intentos_totales)
SELECT id, email, cliente_id, usuario_sistema_id, ip, intentos, ultimo_intento,
       usuarios_distintos, email_bloqueado, ips_bloqueadas, intentos_totales
FROM librospe_db.intentos_login;

INSERT IGNORE INTO librospe_ms_usuarios.bloqueos
    (id, tipo_usuario, usuario_sistema_id, cliente_id, motivo, bloqueado_por,
     fecha_bloqueo, fecha_desbloqueo, desbloqueado_por, estado, permanente, minutos_bloqueo)
SELECT id, tipo_usuario, usuario_sistema_id, cliente_id, motivo, bloqueado_por,
       fecha_bloqueo, fecha_desbloqueo, desbloqueado_por, estado, permanente, minutos_bloqueo
FROM librospe_db.bloqueos;

-- ============================================================
-- 3. MS_VENTAS: cajas, cupones, detalle_pedidos (sin FK)
-- ============================================================
CREATE TABLE IF NOT EXISTS librospe_ms_ventas.cajas (
    id INT(11) NOT NULL AUTO_INCREMENT,
    usuario_id INT(11) NOT NULL,
    monto_inicial DECIMAL(10,2) NULL,
    fecha_apertura DATETIME NULL,
    fecha_cierre DATETIME NULL,
    monto_esperado DECIMAL(10,2) NULL,
    monto_real DECIMAL(10,2) NULL,
    diferencia DECIMAL(10,2) NULL,
    estado VARCHAR(20) NULL,
    PRIMARY KEY (id),
    KEY idx_cajas_usuario (usuario_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS librospe_ms_ventas.cupones (
    id INT(11) NOT NULL AUTO_INCREMENT,
    codigo VARCHAR(50) NOT NULL,
    tipo VARCHAR(20) NULL,
    valor FLOAT NULL,
    minimo_compra FLOAT NULL,
    usos_maximos INT(11) NULL,
    usos_actuales INT(11) NULL,
    fecha_expiracion DATETIME NULL,
    activo TINYINT(1) NULL,
    fecha_creacion DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_cupones_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS librospe_ms_ventas.detalle_pedidos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    pedido_id INT(11) NULL,
    producto_id INT(11) NULL,
    nombre_producto VARCHAR(200) NULL,
    cantidad INT(11) NULL,
    precio_unitario DECIMAL(10,2) NULL,
    subtotal DECIMAL(10,2) NULL,
    PRIMARY KEY (id),
    KEY idx_dps_pedido (pedido_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Carga inicial desde la principal
INSERT IGNORE INTO librospe_ms_ventas.cajas
    (id, usuario_id, monto_inicial, fecha_apertura, fecha_cierre,
     monto_esperado, monto_real, diferencia, estado)
SELECT id, usuario_id, monto_inicial, fecha_apertura, fecha_cierre,
       monto_esperado, monto_real, diferencia, estado
FROM librospe_db.cajas;

INSERT IGNORE INTO librospe_ms_ventas.cupones
    (id, codigo, tipo, valor, minimo_compra, usos_maximos, usos_actuales,
     fecha_expiracion, activo, fecha_creacion)
SELECT id, codigo, tipo, valor, minimo_compra, usos_maximos, usos_actuales,
       fecha_expiracion, activo, fecha_creacion
FROM librospe_db.cupones;

INSERT IGNORE INTO librospe_ms_ventas.detalle_pedidos
    (id, pedido_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
SELECT id, pedido_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal
FROM librospe_db.detalle_pedidos;

-- ============================================================
-- 4. VERIFICACION: conteo de tablas nuevas (debe coincidir
--    con la principal; el sync horario mantiene la igualdad)
-- ============================================================
SELECT 'MS_CLIENTES ruc_empresas ' AS tabla, (SELECT COUNT(*) FROM librospe_ms_clientes.ruc_empresas) AS filas_ms, (SELECT COUNT(*) FROM librospe_db.ruc_empresas) AS filas_principal
UNION ALL SELECT 'MS_CLIENTES departamentos', (SELECT COUNT(*) FROM librospe_ms_clientes.departamentos), (SELECT COUNT(*) FROM librospe_db.departamentos)
UNION ALL SELECT 'MS_CLIENTES provincias   ', (SELECT COUNT(*) FROM librospe_ms_clientes.provincias), (SELECT COUNT(*) FROM librospe_db.provincias)
UNION ALL SELECT 'MS_CLIENTES distritos    ', (SELECT COUNT(*) FROM librospe_ms_clientes.distritos), (SELECT COUNT(*) FROM librospe_db.distritos)
UNION ALL SELECT 'MS_USUARIOS permisos     ', (SELECT COUNT(*) FROM librospe_ms_usuarios.permisos), (SELECT COUNT(*) FROM librospe_db.permisos)
UNION ALL SELECT 'MS_USUARIOS rol_permisos ', (SELECT COUNT(*) FROM librospe_ms_usuarios.rol_permisos), (SELECT COUNT(*) FROM librospe_db.rol_permisos)
UNION ALL SELECT 'MS_USUARIOS auditoria    ', (SELECT COUNT(*) FROM librospe_ms_usuarios.auditoria), (SELECT COUNT(*) FROM librospe_db.auditoria)
UNION ALL SELECT 'MS_USUARIOS intentos     ', (SELECT COUNT(*) FROM librospe_ms_usuarios.intentos_login), (SELECT COUNT(*) FROM librospe_db.intentos_login)
UNION ALL SELECT 'MS_USUARIOS bloqueos     ', (SELECT COUNT(*) FROM librospe_ms_usuarios.bloqueos), (SELECT COUNT(*) FROM librospe_db.bloqueos)
UNION ALL SELECT 'MS_VENTAS cajas          ', (SELECT COUNT(*) FROM librospe_ms_ventas.cajas), (SELECT COUNT(*) FROM librospe_db.cajas)
UNION ALL SELECT 'MS_VENTAS cupones        ', (SELECT COUNT(*) FROM librospe_ms_ventas.cupones), (SELECT COUNT(*) FROM librospe_db.cupones)
UNION ALL SELECT 'MS_VENTAS detalle_pedidos', (SELECT COUNT(*) FROM librospe_ms_ventas.detalle_pedidos), (SELECT COUNT(*) FROM librospe_db.detalle_pedidos);

-- 4.2 Columnas alineadas presentes (debe devolver 31 filas)
SELECT table_schema AS bd, table_name AS tabla, column_name AS columna
FROM information_schema.columns
WHERE (table_schema = 'librospe_ms_usuarios' AND table_name = 'roles' AND column_name IN ('descripcion','estado'))
   OR (table_schema = 'librospe_ms_usuarios' AND table_name = 'usuarios_sistema' AND column_name = 'debe_cambiar_clave')
   OR (table_schema = 'librospe_ms_clientes' AND table_name = 'clientes' AND column_name IN ('token_recuperacion','token_expiracion','puntos','ce','referencia'))
   OR (table_schema = 'librospe_ms_inventario' AND table_name = 'inventario_productos' AND column_name IN ('estado','stock_minimo','stock_maximo','costo'))
   OR (table_schema = 'librospe_ms_inventario' AND table_name = 'inventario_proveedores' AND column_name = 'estado')
   OR (table_schema = 'librospe_ms_ventas' AND table_name = 'comercial_pedidos' AND column_name IN ('nombre_recibe','dni_recibe','fecha_entrega','confirmado_por','cliente_confirmo','fecha_confirmacion_cliente','subtotal','descuento','costo_envio','metodo_pago','codigo_operacion','referencia_entrega'))
   OR (table_schema = 'librospe_ms_ventas' AND table_name = 'comercial_ventas' AND column_name IN ('estado','pedido_id','metodo_pago','monto_recibido','vuelto','cliente_tipo_documento'))
ORDER BY bd, tabla, columna;
