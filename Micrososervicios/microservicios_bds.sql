-- ============================================================
-- PROVISION DE BASES DE DATOS DE MICROSERVICIOS - LibrosPE
-- ------------------------------------------------------------
-- Cada modulo de negocio tiene SU PROPIA base de datos (schema)
-- y solo se comunica con los demas por HTTP (X-Service-Token).
--
-- BDs creadas (idempotente, se puede ejecutar varias veces):
--   librospe_ms_ventas     -> pedidos y ventas
--   librospe_ms_inventario -> productos, categorias y proveedores
--   librospe_ms_usuarios   -> usuarios del sistema y roles
--   librospe_ms_clientes   -> clientes registrados
--
-- Despues de ejecutar este script, configurar en la app:
--   MS_VENTAS_DB=librospe_ms_ventas
--   MS_INVENTARIO_DB=librospe_ms_inventario
--   MS_USUARIOS_DB=librospe_ms_usuarios
--   MS_CLIENTES_DB=librospe_ms_clientes
-- (Sin esas variables la app usa BD principal como fallback.)
-- ============================================================

CREATE DATABASE IF NOT EXISTS librospe_ms_ventas
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS librospe_ms_inventario
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS librospe_ms_usuarios
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS librospe_ms_clientes
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- MICROSERVICIO VENTAS
-- ============================================================
CREATE TABLE IF NOT EXISTS librospe_ms_ventas.comercial_pedidos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    cliente_id INT(11) NOT NULL,
    fecha_pedido DATETIME NULL,
    estado VARCHAR(20) NULL,
    total DECIMAL(10,2) NULL,
    direccion_entrega TEXT NULL,
    tipo_entrega VARCHAR(20) NULL,
    nota TEXT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS librospe_ms_ventas.comercial_detalle_pedido (
    id INT(11) NOT NULL AUTO_INCREMENT,
    pedido_id INT(11) NOT NULL,
    producto_id INT(11) NOT NULL,
    cantidad INT(11) NULL,
    precio_unitario DECIMAL(10,2) NULL,
    subtotal DECIMAL(10,2) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS librospe_ms_ventas.comercial_ventas (
    id INT(11) NOT NULL AUTO_INCREMENT,
    producto_id INT(11) NOT NULL,
    fecha_venta DATETIME NOT NULL,
    cantidad INT(11) NOT NULL DEFAULT 1,
    vendedor_id INT(11) NOT NULL,
    cliente_id INT(11) NULL,
    tipo_comprobante ENUM('boleta','factura') NOT NULL DEFAULT 'boleta',
    numero_comprobante VARCHAR(50) NULL,
    cliente_nombres VARCHAR(100) NULL,
    cliente_apellidos VARCHAR(100) NULL,
    cliente_documento VARCHAR(20) NULL,
    cliente_direccion TEXT NULL,
    cliente_email VARCHAR(150) NULL,
    cliente_direccion_fiscal TEXT NULL,
    cliente_razon_social VARCHAR(200) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Carga inicial desde la BD principal (pedidos y detalles)
INSERT IGNORE INTO librospe_ms_ventas.comercial_pedidos
    (id, cliente_id, fecha_pedido, estado, total, direccion_entrega, tipo_entrega, nota)
SELECT p.id, p.cliente_id, p.fecha_pedido, p.estado, p.total,
       p.direccion_entrega, p.tipo_entrega, p.nota
FROM librospe_db.pedidos p;

INSERT IGNORE INTO librospe_ms_ventas.comercial_detalle_pedido
    (id, pedido_id, producto_id, cantidad, precio_unitario, subtotal)
SELECT dp.id, dp.pedido_id, dp.producto_id, dp.cantidad,
       dp.precio_unitario, dp.subtotal
FROM librospe_db.detalle_pedido dp;

INSERT IGNORE INTO librospe_ms_ventas.comercial_ventas
    (id, producto_id, fecha_venta, cantidad, vendedor_id, cliente_id,
     tipo_comprobante, numero_comprobante, cliente_nombres, cliente_apellidos,
     cliente_documento, cliente_direccion, cliente_email)
SELECT v.id, v.producto_id, v.fecha_venta, v.cantidad, v.vendedor_id, v.cliente_id,
       v.tipo_comprobante, v.numero_comprobante, v.cliente_nombres, v.cliente_apellidos,
       v.cliente_documento, v.cliente_direccion, v.cliente_email
FROM librospe_db.ventas v;

-- ============================================================
-- MICROSERVICIO INVENTARIO
-- ============================================================
CREATE TABLE IF NOT EXISTS librospe_ms_inventario.inventario_categorias (
    id_categoria INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT NULL,
    activo TINYINT(1) DEFAULT 1,
    PRIMARY KEY (id_categoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS librospe_ms_inventario.inventario_productos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT NULL,
    cantidad INT(11) DEFAULT 0,
    proveedor_id INT(11) NULL,
    precio DECIMAL(10,2) DEFAULT 0.00,
    imagen VARCHAR(255) NULL,
    id_categoria INT(11) NULL,
    precio_oferta DECIMAL(10,2) NULL,
    destacado INT(11) DEFAULT 0,
    codigo_barras VARCHAR(50) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS librospe_ms_inventario.inventario_proveedores (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    contacto VARCHAR(20) NOT NULL,
    empresa VARCHAR(150) NULL,
    ruc_empresa_id INT(11) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Carga inicial desde la BD principal
INSERT IGNORE INTO librospe_ms_inventario.inventario_categorias
    (id_categoria, nombre, descripcion, activo)
SELECT id_categoria, nombre, descripcion, activo
FROM librospe_db.categorias;

INSERT IGNORE INTO librospe_ms_inventario.inventario_productos
    (id, nombre, descripcion, cantidad, proveedor_id, precio, imagen,
     id_categoria, precio_oferta, destacado, codigo_barras)
SELECT p.id, p.nombre, p.descripcion, p.cantidad, p.proveedor_id,
       p.precio, p.imagen, p.id_categoria, p.precio_oferta, p.destacado, p.codigo_barras
FROM librospe_db.productos p;

INSERT IGNORE INTO librospe_ms_inventario.inventario_proveedores
    (id, nombre, email, contacto, empresa, ruc_empresa_id)
SELECT pr.id, pr.nombre, pr.email, pr.contacto, pr.nombre, pr.ruc_empresa_id
FROM librospe_db.proveedores pr;

-- ============================================================
-- MICROSERVICIO USUARIOS
-- ============================================================
CREATE TABLE IF NOT EXISTS librospe_ms_usuarios.usuarios_sistema (
    id INT(11) NOT NULL AUTO_INCREMENT,
    correo VARCHAR(150) NOT NULL,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    clave VARCHAR(255) NOT NULL,
    estado TINYINT(1) NOT NULL DEFAULT 1,
    rol_id INT(11) NOT NULL,
    rol VARCHAR(20) DEFAULT 'vendedor',
    documento VARCHAR(20) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_correo (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS librospe_ms_usuarios.roles (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Carga inicial desde la BD principal
INSERT IGNORE INTO librospe_ms_usuarios.usuarios_sistema
    (id, correo, nombres, apellidos, clave, estado, rol_id, rol, documento)
SELECT id, correo, nombres, apellidos, clave, estado, rol_id, rol, documento
FROM librospe_db.usuarios_sistema;

INSERT IGNORE INTO librospe_ms_usuarios.roles
    (id, nombre)
SELECT id, nombre
FROM librospe_db.roles;

-- ============================================================
-- MICROSERVICIO CLIENTES
-- ============================================================
CREATE TABLE IF NOT EXISTS librospe_ms_clientes.clientes (
    id INT(11) NOT NULL AUTO_INCREMENT,
    dni VARCHAR(8) NULL,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    correo VARCHAR(150) NOT NULL,
    telefono VARCHAR(15) NULL,
    direccion TEXT NULL,
    clave VARCHAR(255) NOT NULL,
    fecha_registro DATETIME NULL,
    estado TINYINT(1) NOT NULL DEFAULT 1,
    ruc VARCHAR(11) NULL,
    departamento VARCHAR(100) NULL,
    provincia VARCHAR(100) NULL,
    distrito VARCHAR(150) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_correo (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Carga inicial desde la BD principal (sin la clave si no se necesita,
-- se conserva el hash para compatibilidad con login)
INSERT IGNORE INTO librospe_ms_clientes.clientes
    (id, dni, nombres, apellidos, correo, telefono, direccion, clave,
     fecha_registro, estado, ruc, departamento, provincia, distrito)
SELECT c.id, c.dni, c.nombres, c.apellidos, c.correo, c.telefono, c.direccion,
       c.clave, c.fecha_registro, c.estado, c.ruc, c.departamento, c.provincia, c.distrito
FROM librospe_db.clientes c;

-- ============================================================
-- VERIFICACION
-- ============================================================
SELECT 'VENTAS pedidos'     AS servicio,
       (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_pedidos) AS filas
UNION ALL SELECT 'VENTAS detalles', (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_detalle_pedido)
UNION ALL SELECT 'VENTAS ventas',   (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_ventas)
UNION ALL SELECT 'INVENTARIO productos',   (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_productos)
UNION ALL SELECT 'INVENTARIO categorias',  (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_categorias)
UNION ALL SELECT 'INVENTARIO proveedores', (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_proveedores)
UNION ALL SELECT 'USUARIOS sistema', (SELECT COUNT(*) FROM librospe_ms_usuarios.usuarios_sistema)
UNION ALL SELECT 'USUARIOS roles',   (SELECT COUNT(*) FROM librospe_ms_usuarios.roles)
UNION ALL SELECT 'CLIENTES registrados', (SELECT COUNT(*) FROM librospe_ms_clientes.clientes);