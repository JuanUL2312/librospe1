-- ============================================================
-- MIGRACION_NUEVAS_TABLAS.SQL
-- Agrega las tablas y columnas nuevas del sistema LibrosPE.
-- Compatible con MariaDB / phpMyAdmin (sin DELIMITER).
-- Es SEGURO e IDEMPOTENTE: se puede ejecutar varias veces.
-- ============================================================

USE librospe_db;

-- ============================================================
-- 1. NUEVAS TABLAS (se crean solo si no existen)
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

-- ============================================================
-- 2. NUEVAS COLUMNAS (solo si no existen - MariaDB)
-- ============================================================

ALTER TABLE productos ADD COLUMN IF NOT EXISTS costo DECIMAL(10,2) NULL;
ALTER TABLE usuarios_sistema ADD COLUMN IF NOT EXISTS debe_cambiar_clave TINYINT(1) DEFAULT 0;

-- ============================================================
-- 3. SEED DE PERMISOS (asignados al rol administrador)
-- ============================================================

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

-- FIN DEL SCRIPT
