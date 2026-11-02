-- ============================================================
-- ACTUALIZAR_BD.SQL
-- Actualiza y agrega las tablas / columnas faltantes de la
-- base de datos LibrosPE (Librería Salesiana Don Bosco).
--
-- Es SEGURO e IDEMPOTENTE: se puede ejecutar varias veces,
-- solo crea lo que falta y agrega las columnas que no existen.
--
-- Uso:  SOURCE actualizar_bd.sql;   (o ejecutar en phpMyAdmin)
-- ============================================================

USE librospe_db;

-- ============================================================
-- 0. Procedimiento auxiliar: agregar columna solo si no existe
-- ============================================================
DROP PROCEDURE IF EXISTS add_column_if_not_exists;
DELIMITER $$
CREATE PROCEDURE add_column_if_not_exists(
    IN tbl VARCHAR(64),
    IN col VARCHAR(64),
    IN ddl VARCHAR(255)
)
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name   = tbl
          AND column_name  = col
    ) THEN
        SET @sql = CONCAT('ALTER TABLE `', tbl, '` ADD COLUMN `', col, '` ', ddl);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$
DELIMITER ;

-- ============================================================
-- 1. TABLAS QUE PUEDEN FALTAR (se crean si no existen)
-- ============================================================

-- roles
CREATE TABLE IF NOT EXISTS roles (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT NULL,
    estado TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- usuarios_sistema
CREATE TABLE IF NOT EXISTS usuarios_sistema (
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

-- categorias
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT NULL,
    activo TINYINT(1) DEFAULT 1,
    PRIMARY KEY (id_categoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- proveedores
CREATE TABLE IF NOT EXISTS proveedores (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    contacto VARCHAR(20) NOT NULL,
    ruc_empresa_id INT(11) NULL,
    estado TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- productos
CREATE TABLE IF NOT EXISTS productos (
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
    estado TINYINT(1) NOT NULL DEFAULT 1,
    stock_minimo INT(11) DEFAULT 5,
    stock_maximo INT(11) DEFAULT 100,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- clientes
CREATE TABLE IF NOT EXISTS clientes (
    id INT(11) NOT NULL AUTO_INCREMENT,
    dni VARCHAR(8) NULL,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    correo VARCHAR(150) NOT NULL,
    telefono VARCHAR(15) NULL,
    direccion TEXT NULL,
    clave VARCHAR(255) NOT NULL,
    fecha_registro DATETIME NULL,
    token_recuperacion VARCHAR(100) NULL,
    token_expiracion DATETIME NULL,
    puntos INT(11) DEFAULT 0,
    estado TINYINT(1) NOT NULL DEFAULT 1,
    ruc VARCHAR(11) NULL,
    departamento VARCHAR(100) NULL,
    provincia VARCHAR(100) NULL,
    distrito VARCHAR(150) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_correo (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- departamentos / provincias / distritos (ubigeo)
CREATE TABLE IF NOT EXISTS departamentos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    ubigeo VARCHAR(2) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS provincias (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    ubigeo VARCHAR(4) NULL,
    departamento_id INT(11) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS distritos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(150) NOT NULL,
    ubigeo VARCHAR(6) NULL,
    provincia_id INT(11) NULL,
    departamento_id INT(11) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ruc_empresas
CREATE TABLE IF NOT EXISTS ruc_empresas (
    id INT(11) NOT NULL AUTO_INCREMENT,
    ruc VARCHAR(11) NOT NULL,
    razon_social VARCHAR(200) NOT NULL,
    nombre_comercial VARCHAR(150) NULL,
    direccion TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ruc (ruc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- pedidos
CREATE TABLE IF NOT EXISTS pedidos (
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

-- detalle_pedido
CREATE TABLE IF NOT EXISTS detalle_pedido (
    id INT(11) NOT NULL AUTO_INCREMENT,
    pedido_id INT(11) NOT NULL,
    producto_id INT(11) NOT NULL,
    cantidad INT(11) NULL,
    precio_unitario DECIMAL(10,2) NULL,
    subtotal DECIMAL(10,2) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ventas
CREATE TABLE IF NOT EXISTS ventas (
    id INT(11) NOT NULL AUTO_INCREMENT,
    producto_id INT(11) NOT NULL,
    fecha_venta DATETIME NOT NULL,
    cantidad INT(11) NOT NULL DEFAULT 1,
    vendedor_id INT(11) NOT NULL,
    cliente_id INT(11) NULL,
    tipo_comprobante ENUM('boleta','factura') NOT NULL DEFAULT 'boleta',
    numero_comprobante VARCHAR(50) NULL,
    estado TINYINT(1) NOT NULL DEFAULT 1,
    cliente_nombres VARCHAR(100) NULL,
    cliente_apellidos VARCHAR(100) NULL,
    cliente_documento VARCHAR(20) NULL,
    cliente_email VARCHAR(150) NULL,
    cliente_direccion TEXT NULL,
    cliente_direccion_fiscal TEXT NULL,
    cliente_razon_social VARCHAR(200) NULL,
    pedido_id INT(11) NULL,
    metodo_pago VARCHAR(20) NULL,
    monto_recibido DECIMAL(10,2) NULL,
    vuelto DECIMAL(10,2) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- cajas (apertura / cierre)
CREATE TABLE IF NOT EXISTS cajas (
    id INT(11) NOT NULL AUTO_INCREMENT,
    usuario_id INT(11) NOT NULL,
    monto_inicial DECIMAL(10,2) NULL,
    fecha_apertura DATETIME NULL,
    fecha_cierre DATETIME NULL,
    monto_esperado DECIMAL(10,2) NULL,
    monto_real DECIMAL(10,2) NULL,
    diferencia DECIMAL(10,2) NULL,
    estado VARCHAR(20) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- intentos_login
CREATE TABLE IF NOT EXISTS intentos_login (
    id INT(11) NOT NULL AUTO_INCREMENT,
    email VARCHAR(150) NULL,
    cliente_id INT(11) NULL,
    usuario_sistema_id INT(11) NULL,
    ip VARCHAR(45) NULL,
    intentos INT(11) DEFAULT 1,
    ultimo_intento DATETIME DEFAULT CURRENT_TIMESTAMP,
    usuarios_distintos INT(11) DEFAULT 0,
    email_bloqueado DATETIME NULL,
    ips_bloqueadas DATETIME NULL,
    intentos_totales INT(11) DEFAULT 0,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- bloqueos
CREATE TABLE IF NOT EXISTS bloqueos (
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
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Microservicio COMERCIAL
CREATE TABLE IF NOT EXISTS comercial_pedidos (
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

CREATE TABLE IF NOT EXISTS comercial_detalle_pedido (
    id INT(11) NOT NULL AUTO_INCREMENT,
    pedido_id INT(11) NOT NULL,
    producto_id INT(11) NOT NULL,
    cantidad INT(11) NULL,
    precio_unitario DECIMAL(10,2) NULL,
    subtotal DECIMAL(10,2) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS comercial_ventas (
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

-- Microservicio INVENTARIO
CREATE TABLE IF NOT EXISTS inventario_categorias (
    id_categoria INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT NULL,
    activo TINYINT(1) DEFAULT 1,
    PRIMARY KEY (id_categoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inventario_productos (
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

CREATE TABLE IF NOT EXISTS inventario_proveedores (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    contacto VARCHAR(20) NOT NULL,
    empresa VARCHAR(150) NULL,
    ruc_empresa_id INT(11) NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 2. AGREGAR COLUMNAS FALTANTES (solo si no existen)
-- ============================================================
CALL add_column_if_not_exists('clientes', 'ruc', 'VARCHAR(11) NULL');
CALL add_column_if_not_exists('clientes', 'departamento', 'VARCHAR(100) NULL');
CALL add_column_if_not_exists('clientes', 'provincia', 'VARCHAR(100) NULL');
CALL add_column_if_not_exists('clientes', 'distrito', 'VARCHAR(150) NULL');

CALL add_column_if_not_exists('usuarios_sistema', 'documento', 'VARCHAR(20) NULL');
CALL add_column_if_not_exists('usuarios_sistema', 'rol', "VARCHAR(20) DEFAULT 'vendedor'");

CALL add_column_if_not_exists('productos', 'estado', 'TINYINT(1) NOT NULL DEFAULT 1');
CALL add_column_if_not_exists('productos', 'stock_minimo', 'INT(11) DEFAULT 5');
CALL add_column_if_not_exists('productos', 'stock_maximo', 'INT(11) DEFAULT 100');

CALL add_column_if_not_exists('ventas', 'metodo_pago', 'VARCHAR(20) NULL');
CALL add_column_if_not_exists('ventas', 'monto_recibido', 'DECIMAL(10,2) NULL');
CALL add_column_if_not_exists('ventas', 'vuelto', 'DECIMAL(10,2) NULL');
CALL add_column_if_not_exists('ventas', 'pedido_id', 'INT(11) NULL');
CALL add_column_if_not_exists('ventas', 'cliente_direccion_fiscal', 'TEXT NULL');
CALL add_column_if_not_exists('ventas', 'cliente_razon_social', 'VARCHAR(200) NULL');

CALL add_column_if_not_exists('intentos_login', 'email_bloqueado', 'DATETIME NULL');
CALL add_column_if_not_exists('intentos_login', 'ips_bloqueadas', 'DATETIME NULL');
CALL add_column_if_not_exists('intentos_login', 'intentos_totales', 'INT(11) DEFAULT 0');

CALL add_column_if_not_exists('bloqueos', 'permanente', 'TINYINT(1) DEFAULT 0');
CALL add_column_if_not_exists('bloqueos', 'minutos_bloqueo', 'INT(11) NULL');

-- ============================================================
-- 3. VISTAS
-- ============================================================
CREATE OR REPLACE VIEW vista_comercial AS
SELECT
    p.id AS pedido_id,
    p.cliente_id AS cliente_id,
    p.fecha_pedido AS fecha_pedido,
    p.estado AS estado,
    p.total AS total,
    d.producto_id AS producto_id,
    d.cantidad AS cantidad,
    d.precio_unitario AS precio_unitario,
    d.subtotal AS subtotal
FROM comercial_pedidos p
LEFT JOIN comercial_detalle_pedido d ON d.pedido_id = p.id;

CREATE OR REPLACE VIEW v_usuarios_bloqueados AS
SELECT
    b.id,
    b.tipo_usuario,
    b.usuario_sistema_id,
    b.cliente_id,
    b.motivo,
    b.fecha_bloqueo,
    b.bloqueado_por,
    b.fecha_desbloqueo,
    b.desbloqueado_por,
    b.estado,
    COALESCE(
        CONCAT(u.nombres, ' ', u.apellidos),
        CONCAT(c.nombres, ' ', c.apellidos)
    ) AS nombre_completo,
    COALESCE(u.correo, c.correo) AS correo,
    CONCAT(bp.nombres, ' ', bp.apellidos) AS bloqueado_por_nombre,
    CONCAT(dp.nombres, ' ', dp.apellidos) AS desbloqueado_por_nombre,
    CASE WHEN b.estado = 1 AND b.permanente = 1 THEN 'PERMANENTE'
         WHEN b.estado = 1 THEN 'BLOQUEADO'
         ELSE 'ACTIVO' END AS estado_texto
FROM bloqueos b
LEFT JOIN usuarios_sistema u  ON u.id  = b.usuario_sistema_id
LEFT JOIN clientes c          ON c.id  = b.cliente_id
LEFT JOIN usuarios_sistema bp ON bp.id = b.bloqueado_por
LEFT JOIN usuarios_sistema dp ON dp.id = b.desbloqueado_por;

-- ============================================================
-- Limpiar el procedimiento auxiliar (opcional)
-- ============================================================
DROP PROCEDURE IF EXISTS add_column_if_not_exists;

-- FIN DEL SCRIPT
