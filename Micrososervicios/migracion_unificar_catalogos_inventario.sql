-- Unifica categorias/proveedores en librospe_ms_inventario.
-- Las tablas canonicas son `categorias` y `proveedores` (las usa el Gateway).
-- Ejecutar primero en staging o con un respaldo reciente. No borra tablas.
-- Los SELECT iniciales muestran IDs con contenido distinto que requieren
-- reconciliacion manual antes de retirar las tablas antiguas.

-- Categorias con el mismo ID pero diferente nombre: revisar antes de continuar.
SELECT s.id_categoria, s.nombre AS nombre_legacy, d.nombre AS nombre_canonico
FROM librospe_ms_inventario.inventario_categorias s
JOIN librospe_ms_inventario.categorias d USING (id_categoria)
WHERE NOT (s.nombre <=> d.nombre)
   OR NOT (s.descripcion <=> d.descripcion)
   OR NOT (s.activo <=> d.activo);

-- Proveedores con el mismo ID pero datos distintos: revisar antes de continuar.
SELECT s.id, s.nombre AS nombre_legacy, d.nombre AS nombre_canonico,
       s.email AS email_legacy, d.email AS email_canonico,
       s.contacto AS contacto_legacy, d.contacto AS contacto_canonico,
       s.ruc_empresa_id AS ruc_legacy, d.ruc_empresa_id AS ruc_canonico,
       s.estado AS estado_legacy, d.estado AS estado_canonico
FROM librospe_ms_inventario.inventario_proveedores s
JOIN librospe_ms_inventario.proveedores d USING (id)
WHERE NOT (s.nombre <=> d.nombre)
   OR NOT (s.email <=> d.email)
   OR NOT (s.contacto <=> d.contacto)
   OR NOT (s.ruc_empresa_id <=> d.ruc_empresa_id)
   OR NOT (s.estado <=> d.estado);

-- IDs de proveedor usados por productos que no existen en la tabla canonica.
SELECT DISTINCT p.proveedor_id
FROM librospe_ms_inventario.inventario_productos p
LEFT JOIN librospe_ms_inventario.proveedores v ON v.id = p.proveedor_id
WHERE p.proveedor_id IS NOT NULL AND v.id IS NULL;

-- A?ade a la tabla canonica el campo que esperaba el API del microservicio.
SET @empresa_existe := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = 'librospe_ms_inventario'
    AND table_name = 'proveedores' AND column_name = 'empresa'
);
SET @ddl_empresa := IF(
  @empresa_existe = 0,
  'ALTER TABLE librospe_ms_inventario.proveedores ADD COLUMN empresa VARCHAR(150) NULL',
  'SELECT 1'
);
PREPARE stmt_empresa FROM @ddl_empresa;
EXECUTE stmt_empresa;
DEALLOCATE PREPARE stmt_empresa;

-- Copia solo IDs ausentes; no sobrescribe registros canonicos existentes.
INSERT INTO librospe_ms_inventario.categorias
    (id_categoria, nombre, descripcion, activo)
SELECT s.id_categoria, s.nombre, s.descripcion, s.activo
FROM librospe_ms_inventario.inventario_categorias s
LEFT JOIN librospe_ms_inventario.categorias d USING (id_categoria)
WHERE d.id_categoria IS NULL;

INSERT INTO librospe_ms_inventario.proveedores
    (id, nombre, email, contacto, ruc_empresa_id, estado, empresa)
SELECT s.id, s.nombre, s.email, s.contacto, s.ruc_empresa_id, s.estado, s.empresa
FROM librospe_ms_inventario.inventario_proveedores s
LEFT JOIN librospe_ms_inventario.proveedores d USING (id)
WHERE d.id IS NULL;

-- Conserva el dato `empresa` de la tabla anterior cuando el canonico no lo tenia.
UPDATE librospe_ms_inventario.proveedores d
JOIN librospe_ms_inventario.inventario_proveedores s USING (id)
SET d.empresa = s.empresa
WHERE (d.empresa IS NULL OR d.empresa = '') AND s.empresa IS NOT NULL;

-- Verificacion posterior: idealmente ambos conteos de diferencias dan cero.
SELECT COUNT(*) AS categorias_legacy_sin_destino
FROM librospe_ms_inventario.inventario_categorias s
LEFT JOIN librospe_ms_inventario.categorias d USING (id_categoria)
WHERE d.id_categoria IS NULL;
SELECT COUNT(*) AS proveedores_legacy_sin_destino
FROM librospe_ms_inventario.inventario_proveedores s
LEFT JOIN librospe_ms_inventario.proveedores d USING (id)
WHERE d.id IS NULL;

-- No eliminar las tablas legacy hasta revisar los conflictos iniciales,
-- confirmar la aplicacion en produccion y conservar un respaldo.
-- Despues de validar, ejecutar manualmente:
-- DROP TABLE librospe_ms_inventario.inventario_categorias;
-- DROP TABLE librospe_ms_inventario.inventario_proveedores;
