-- ============================================================
-- BD_MONOLITO - Esquema completo de la base de datos DEL MONOLITO
-- Librería Salesiana Don Bosco (LibrosPE) - version MONOLITICA pura
-- BD propia y separada: librospe_monolito (NO se comparte con microservicios)
-- Motor: MySQL / MariaDB
-- ============================================================

CREATE DATABASE IF NOT EXISTS librospe_monolito
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE librospe_monolito;

-- ============================================================
-- 1. roles
-- ============================================================
CREATE TABLE IF NOT EXISTS roles (
    id          INT(11)      NOT NULL AUTO_INCREMENT,
    nombre      VARCHAR(50)  NOT NULL,
    descripcion TEXT         NULL,
    estado      TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 2. usuarios_sistema
-- ============================================================
CREATE TABLE IF NOT EXISTS usuarios_sistema (
    id        INT(11)      NOT NULL AUTO_INCREMENT,
    correo    VARCHAR(150) NOT NULL,
    nombres   VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    clave     VARCHAR(255) NOT NULL,
    estado    TINYINT(1)   NOT NULL DEFAULT 1,
    rol_id    INT(11)      NOT NULL,
    rol       VARCHAR(20)  DEFAULT 'vendedor',
    documento VARCHAR(20)  NULL, -- DNI o Carnet de Extranjería
    PRIMARY KEY (id),
    UNIQUE KEY uq_correo (correo),
    CONSTRAINT fk_usuarios_rol FOREIGN KEY (rol_id) REFERENCES roles (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 3. categorias
-- ============================================================
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria INT(11)     NOT NULL AUTO_INCREMENT,
    nombre       VARCHAR(50) NOT NULL,
    descripcion  TEXT        NULL,
    activo       TINYINT(1)  DEFAULT 1,
    PRIMARY KEY (id_categoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 4. proveedores
-- ============================================================
CREATE TABLE IF NOT EXISTS proveedores (
    id            INT(11)      NOT NULL AUTO_INCREMENT,
    nombre        VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL,
    contacto      VARCHAR(20)  NOT NULL,
    ruc_empresa_id INT(11)     NULL,
    estado        TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 5. productos
-- ============================================================
CREATE TABLE IF NOT EXISTS productos (
    id            INT(11)       NOT NULL AUTO_INCREMENT,
    nombre        VARCHAR(150)  NOT NULL,
    descripcion   TEXT          NULL,
    cantidad      INT(11)       DEFAULT 0,
    proveedor_id  INT(11)       NULL,
    precio        DECIMAL(10,2) DEFAULT 0.00,
    imagen        VARCHAR(255)  NULL,
    id_categoria  INT(11)       NULL,
    precio_oferta DECIMAL(10,2) NULL,
    destacado     INT(11)       DEFAULT 0,
    codigo_barras VARCHAR(50)   NULL,
    estado        TINYINT(1)    NOT NULL DEFAULT 1,
    stock_minimo  INT(11)       DEFAULT 5,   -- umbral de alerta de stock bajo
    stock_maximo  INT(11)       DEFAULT 100, -- umbral de alerta de exceso
    PRIMARY KEY (id),
    CONSTRAINT fk_productos_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores (id),
    CONSTRAINT fk_productos_categoria FOREIGN KEY (id_categoria) REFERENCES categorias (id_categoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 6. clientes
-- ============================================================
CREATE TABLE IF NOT EXISTS clientes (
    id                INT(11)      NOT NULL AUTO_INCREMENT,
    dni               VARCHAR(8)   NULL,
    nombres           VARCHAR(100) NOT NULL,
    apellidos         VARCHAR(100) NOT NULL,
    correo            VARCHAR(150) NOT NULL,
    telefono          VARCHAR(15)  NULL,
    direccion         TEXT         NULL,
    clave             VARCHAR(255) NOT NULL,
    fecha_registro    DATETIME     NULL,
    token_recuperacion VARCHAR(100) NULL,
    token_expiracion  DATETIME     NULL,
    puntos            INT(11)      DEFAULT 0,
    estado            TINYINT(1)   NOT NULL DEFAULT 1,
    ruc               VARCHAR(11)  NULL,
    departamento      VARCHAR(100) NULL,
    provincia         VARCHAR(100) NULL,
    distrito          VARCHAR(150) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_correo (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 7. departamentos / provincias / distritos (ubigeo Perú)
-- ============================================================
CREATE TABLE IF NOT EXISTS departamentos (
    id     INT(11)      NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    ubigeo VARCHAR(2)   NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS provincias (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    nombre          VARCHAR(100) NOT NULL,
    ubigeo          VARCHAR(4)   NULL,
    departamento_id INT(11)      NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_provincias_departamento FOREIGN KEY (departamento_id) REFERENCES departamentos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS distritos (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    nombre          VARCHAR(150) NOT NULL,
    ubigeo          VARCHAR(6)   NULL,
    provincia_id    INT(11)      NULL,
    departamento_id INT(11)      NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_distritos_provincia    FOREIGN KEY (provincia_id)    REFERENCES provincias (id),
    CONSTRAINT fk_distritos_departamento FOREIGN KEY (departamento_id) REFERENCES departamentos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 8. ruc_empresas
-- ============================================================
CREATE TABLE IF NOT EXISTS ruc_empresas (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    ruc             VARCHAR(11)  NOT NULL,
    razon_social    VARCHAR(200) NOT NULL,
    nombre_comercial VARCHAR(150) NULL,
    direccion       TEXT         NULL,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ruc (ruc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 9. pedidos (tienda online)
-- ============================================================
CREATE TABLE IF NOT EXISTS pedidos (
    id                INT(11)     NOT NULL AUTO_INCREMENT,
    cliente_id        INT(11)     NOT NULL,
    fecha_pedido      DATETIME    NULL,
    estado            VARCHAR(20) NULL,
    total             DECIMAL(10,2) NULL,
    direccion_entrega TEXT        NULL,
    tipo_entrega      VARCHAR(20) NULL,
    nota              TEXT        NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_pedidos_cliente FOREIGN KEY (cliente_id) REFERENCES clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 10. detalle_pedido
-- ============================================================
CREATE TABLE IF NOT EXISTS detalle_pedido (
    id             INT(11)       NOT NULL AUTO_INCREMENT,
    pedido_id      INT(11)       NOT NULL,
    producto_id    INT(11)       NOT NULL,
    cantidad       INT(11)       NULL,
    precio_unitario DECIMAL(10,2) NULL,
    subtotal       DECIMAL(10,2) NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_detalle_pedido FOREIGN KEY (pedido_id)   REFERENCES pedidos (id),
    CONSTRAINT fk_detalle_producto FOREIGN KEY (producto_id) REFERENCES productos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 11. ventas (POS / tienda)
-- ============================================================
CREATE TABLE IF NOT EXISTS ventas (
    id                   INT(11)       NOT NULL AUTO_INCREMENT,
    producto_id          INT(11)       NOT NULL,
    fecha_venta          DATETIME      NOT NULL,
    cantidad             INT(11)       NOT NULL DEFAULT 1,
    vendedor_id          INT(11)       NOT NULL,
    cliente_id           INT(11)       NULL,
    tipo_comprobante     ENUM('boleta','factura') NOT NULL DEFAULT 'boleta',
    numero_comprobante   VARCHAR(50)   NULL,
    estado               TINYINT(1)    NOT NULL DEFAULT 1,
    cliente_nombres      VARCHAR(100)  NULL,
    cliente_apellidos    VARCHAR(100)  NULL,
    cliente_documento    VARCHAR(20)   NULL,
    cliente_email        VARCHAR(150)  NULL,
    cliente_direccion    TEXT          NULL,
    cliente_direccion_fiscal TEXT      NULL,
    cliente_razon_social VARCHAR(200)  NULL,
    pedido_id            INT(11)       NULL,
    metodo_pago          VARCHAR(20)   NULL, -- efectivo, tarjeta, yape, plin
    monto_recibido       DECIMAL(10,2) NULL,
    vuelto               DECIMAL(10,2) NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_ventas_producto  FOREIGN KEY (producto_id)  REFERENCES productos (id),
    CONSTRAINT fk_ventas_vendedor FOREIGN KEY (vendedor_id)  REFERENCES usuarios_sistema (id),
    CONSTRAINT fk_ventas_cliente  FOREIGN KEY (cliente_id)  REFERENCES clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 12. cajas (apertura / cierre)
-- ============================================================
CREATE TABLE IF NOT EXISTS cajas (
    id             INT(11)       NOT NULL AUTO_INCREMENT,
    usuario_id     INT(11)       NOT NULL,
    monto_inicial  DECIMAL(10,2) NULL,
    fecha_apertura DATETIME      NULL,
    fecha_cierre   DATETIME      NULL,
    monto_esperado DECIMAL(10,2) NULL,
    monto_real     DECIMAL(10,2) NULL,
    diferencia     DECIMAL(10,2) NULL,
    estado         VARCHAR(20)   NULL, -- abierta / cerrada
    PRIMARY KEY (id),
    CONSTRAINT fk_cajas_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios_sistema (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 13. intentos_login (seguridad)
-- ============================================================
CREATE TABLE IF NOT EXISTS intentos_login (
    id               INT(11)      NOT NULL AUTO_INCREMENT,
    email            VARCHAR(150) NULL,
    cliente_id       INT(11)      NULL,
    usuario_sistema_id INT(11)    NULL,
    ip               VARCHAR(45)  NULL,
    intentos         INT(11)      DEFAULT 1,
    ultimo_intento   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    usuarios_distintos INT(11)    DEFAULT 0,
    email_bloqueado  DATETIME     NULL,
    ips_bloqueadas   DATETIME     NULL,
    intentos_totales INT(11)      DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT fk_intentos_cliente  FOREIGN KEY (cliente_id)       REFERENCES clientes (id),
    CONSTRAINT fk_intentos_usuario  FOREIGN KEY (usuario_sistema_id) REFERENCES usuarios_sistema (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 14. bloqueos
-- ============================================================
CREATE TABLE IF NOT EXISTS bloqueos (
    id               INT(11)      NOT NULL AUTO_INCREMENT,
    tipo_usuario     ENUM('sistema','cliente') NOT NULL,
    usuario_sistema_id INT(11)    NULL,
    cliente_id       INT(11)      NULL,
    motivo           VARCHAR(255) NULL,
    bloqueado_por    INT(11)      NULL,
    fecha_bloqueo    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_desbloqueo DATETIME     NULL,
    desbloqueado_por INT(11)      NULL,
    estado           TINYINT(1)   NOT NULL DEFAULT 1,
    permanente       TINYINT(1)   DEFAULT 0,
    minutos_bloqueo  INT(11)      NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_bloqueos_usuario  FOREIGN KEY (usuario_sistema_id) REFERENCES usuarios_sistema (id),
    CONSTRAINT fk_bloqueos_cliente   FOREIGN KEY (cliente_id)       REFERENCES clientes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 15-17. TABLAS DE SEGURIDAD EXTENDIDA (permisos y auditoria)
-- ============================================================
CREATE TABLE IF NOT EXISTS permisos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    descripcion VARCHAR(200) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_permiso_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS rol_permisos (
    id INT(11) NOT NULL AUTO_INCREMENT,
    rol_id INT(11) NOT NULL,
    permiso_id INT(11) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_rol_permiso (rol_id, permiso_id),
    CONSTRAINT fk_rp_rol FOREIGN KEY (rol_id) REFERENCES roles (id),
    CONSTRAINT fk_rp_permiso FOREIGN KEY (permiso_id) REFERENCES permisos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS auditoria (
    id INT(11) NOT NULL AUTO_INCREMENT,
    usuario_id INT(11) NULL,
    accion VARCHAR(50) NOT NULL,
    modulo VARCHAR(50) NOT NULL,
    detalle TEXT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_auditoria_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios_sistema (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE productos ADD COLUMN costo DECIMAL(10,2) NULL;
ALTER TABLE usuarios_sistema ADD COLUMN debe_cambiar_clave TINYINT(1) DEFAULT 0;

INSERT IGNORE INTO permisos (nombre, descripcion) VALUES
('gestionar_productos',  'Crear, editar y eliminar productos'),
('gestionar_proveedores','Crear, editar y eliminar proveedores'),
('gestionar_usuarios',   'Gestionar usuarios del sistema'),
('ver_dashboard',        'Ver el dashboard'),
('ver_caja',             'Abrir y cerrar caja'),
('ver_auditoria',        'Ver registro de auditoría'),
('ver_reportes',         'Ver reportes y exportar'),
('gestionar_bloqueos',   'Gestionar bloqueos de seguridad');

INSERT IGNORE INTO rol_permisos (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permisos p
WHERE r.nombre IN ('admin', 'administrador');

-- ============================================================
-- VISTAS (solo las del monolito; sin vista_comercial de microservicios)
-- ============================================================

-- 24. v_usuarios_bloqueados: bloqueos con nombres y estado
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
