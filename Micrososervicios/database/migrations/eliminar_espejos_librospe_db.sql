-- ============================================================
-- ELIMINAR TABLAS ESPEJO DE librospe_db - Producción real
-- ------------------------------------------------------------
-- Estas 6 tablas son espejos duplicados que fueron creados en
-- BD_Libros.sql y mantenidos por sincronizar.sql (secciones 1-5)
-- para el dashboard. En producción real el gateway lee directo
-- de los binds (librospe_ms_ventas / librospe_ms_inventario)
-- via SQLALCHEMY_BINDS (www/app.py:107), por lo que ya no son
-- necesarias en librospe_db.
--
-- ADVERTENCIA: Ejecutar solo DESPUES de verificar que
-- /microservicios/dashboard y /api/health funcionan con binds
-- y que verificar_microservicios.sql da 21 tablas en MS.
--
-- El gateway seguirá usando las 19 tablas core de librospe_db:
-- auditoria, bloqueos, cajas, categorias, clientes (lectura login),
-- departamentos, detalle_pedido, distritos, intentos_login, pedidos,
-- permisos, productos, proveedores, provincias, rol_permisos, roles,
-- ruc_empresas, usuarios_sistema, ventas
-- ============================================================

USE librospe_db;

-- Ventas espejo (ahora en librospe_ms_ventas)
DROP TABLE IF EXISTS comercial_pedidos;
DROP TABLE IF EXISTS comercial_detalle_pedido;
DROP TABLE IF EXISTS comercial_ventas;

-- Inventario espejo (ahora en librospe_ms_inventario)
DROP TABLE IF EXISTS inventario_categorias;
DROP TABLE IF EXISTS inventario_productos;
DROP TABLE IF EXISTS inventario_proveedores;

-- Verificación: deben quedar 19 tablas core + 0 espejos
SELECT 'Tablas restantes en librospe_db' AS estado, COUNT(*) AS total
FROM information_schema.tables WHERE table_schema = 'librospe_db';

SELECT table_name FROM information_schema.tables
WHERE table_schema = 'librospe_db' ORDER BY table_name;
