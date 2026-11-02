-- ============================================================
-- VERIFICACION DE LA CONEXION ENTRE BD PRINCIPAL Y MICROSERVICIOS
-- ------------------------------------------------------------
-- La conexion entre librospe_db (monolito) y las BDs de
-- microservicio se demuestra asi:
--  1) Cada BD de microservicio tiene SOLO las tablas de su dominio.
--  2) Los datos son los MISMOS que en la BD principal (copia/sync).
--  3) Los IDs (claves primarias) coinciden 1 a 1 -> es la MISMA
--     informacion distribuida, no datos inventados.
--  4) /api/health (monitor) verifica en information_schema que la
--     tabla representativa de cada servicio existe en SU BD.
-- ============================================================

-- 1) BDs de microservicio y sus tablas
SELECT '== TABLAS POR MICROSERVICIO ==' AS ','; -- marcador
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('librospe_ms_ventas','librospe_ms_inventario','librospe_ms_usuarios','librospe_ms_clientes')
ORDER BY table_schema, table_name;

-- 2) Coincidencia de volumen: la principal vs el microservicio
SELECT 'MAPA' AS conexion, 'tabla_principal' AS origen, 'tabla_ms' AS ms, 'filas_principal' AS a, 'filas_ms' AS b, 'coinciden' AS check_resultado
UNION ALL
SELECT 'pedidos    ', 'pedidos', 'comercial_pedidos        ', (SELECT COUNT(*) FROM librospe_db.pedidos), (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_pedidos), (SELECT COUNT(*) FROM librospe_db.pedidos)= (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_pedidos)
UNION ALL
SELECT 'detalle    ', 'detalle_pedido', 'comercial_detalle_pedido', (SELECT COUNT(*) FROM librospe_db.detalle_pedido), (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_detalle_pedido), (SELECT COUNT(*) FROM librospe_db.detalle_pedido)= (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_detalle_pedido)
UNION ALL
SELECT 'ventas     ', 'ventas', 'comercial_ventas         ', (SELECT COUNT(*) FROM librospe_db.ventas), (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_ventas), (SELECT COUNT(*) FROM librospe_db.ventas)= (SELECT COUNT(*) FROM librospe_ms_ventas.comercial_ventas)
UNION ALL
SELECT 'productos  ', 'productos', 'inventario_productos     ', (SELECT COUNT(*) FROM librospe_db.productos), (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_productos), (SELECT COUNT(*) FROM librospe_db.productos)= (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_productos)
UNION ALL
SELECT 'categorias ', 'categorias', 'inventario_categorias    ', (SELECT COUNT(*) FROM librospe_db.categorias), (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_categorias), (SELECT COUNT(*) FROM librospe_db.categorias)= (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_categorias)
UNION ALL
SELECT 'proveedores', 'proveedores', 'inventario_proveedores  ', (SELECT COUNT(*) FROM librospe_db.proveedores), (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_proveedores), (SELECT COUNT(*) FROM librospe_db.proveedores)= (SELECT COUNT(*) FROM librospe_ms_inventario.inventario_proveedores)
UNION ALL
SELECT 'usuarios   ', 'usuarios_sistema', 'usuarios_sistema       ', (SELECT COUNT(*) FROM librospe_db.usuarios_sistema), (SELECT COUNT(*) FROM librospe_ms_usuarios.usuarios_sistema), (SELECT COUNT(*) FROM librospe_db.usuarios_sistema)= (SELECT COUNT(*) FROM librospe_ms_usuarios.usuarios_sistema)
UNION ALL
SELECT 'roles      ', 'roles', 'roles                  ', (SELECT COUNT(*) FROM librospe_db.roles), (SELECT COUNT(*) FROM librospe_ms_usuarios.roles), (SELECT COUNT(*) FROM librospe_db.roles)= (SELECT COUNT(*) FROM librospe_ms_usuarios.roles)
UNION ALL
SELECT 'clientes   ', 'clientes', 'clientes               ', (SELECT COUNT(*) FROM librospe_db.clientes), (SELECT COUNT(*) FROM librospe_ms_clientes.clientes), (SELECT COUNT(*) FROM librospe_db.clientes)= (SELECT COUNT(*) FROM librospe_ms_clientes.clientes)
UNION ALL
SELECT 'cajas      ', 'cajas', 'cajas                  ', (SELECT COUNT(*) FROM librospe_db.cajas), (SELECT COUNT(*) FROM librospe_ms_ventas.cajas), (SELECT COUNT(*) FROM librospe_db.cajas)= (SELECT COUNT(*) FROM librospe_ms_ventas.cajas)
UNION ALL
SELECT 'cupones    ', 'cupones', 'cupones                ', (SELECT COUNT(*) FROM librospe_db.cupones), (SELECT COUNT(*) FROM librospe_ms_ventas.cupones), (SELECT COUNT(*) FROM librospe_db.cupones)= (SELECT COUNT(*) FROM librospe_ms_ventas.cupones)
UNION ALL
SELECT 'det_peds   ', 'detalle_pedidos', 'detalle_pedidos        ', (SELECT COUNT(*) FROM librospe_db.detalle_pedidos), (SELECT COUNT(*) FROM librospe_ms_ventas.detalle_pedidos), (SELECT COUNT(*) FROM librospe_db.detalle_pedidos)= (SELECT COUNT(*) FROM librospe_ms_ventas.detalle_pedidos)
UNION ALL
SELECT 'permisos   ', 'permisos', 'permisos               ', (SELECT COUNT(*) FROM librospe_db.permisos), (SELECT COUNT(*) FROM librospe_ms_usuarios.permisos), (SELECT COUNT(*) FROM librospe_db.permisos)= (SELECT COUNT(*) FROM librospe_ms_usuarios.permisos)
UNION ALL
SELECT 'rol_perm   ', 'rol_permisos', 'rol_permisos           ', (SELECT COUNT(*) FROM librospe_db.rol_permisos), (SELECT COUNT(*) FROM librospe_ms_usuarios.rol_permisos), (SELECT COUNT(*) FROM librospe_db.rol_permisos)= (SELECT COUNT(*) FROM librospe_ms_usuarios.rol_permisos)
UNION ALL
SELECT 'auditoria  ', 'auditoria', 'auditoria              ', (SELECT COUNT(*) FROM librospe_db.auditoria), (SELECT COUNT(*) FROM librospe_ms_usuarios.auditoria), (SELECT COUNT(*) FROM librospe_db.auditoria)= (SELECT COUNT(*) FROM librospe_ms_usuarios.auditoria)
UNION ALL
SELECT 'intentos   ', 'intentos_login', 'intentos_login         ', (SELECT COUNT(*) FROM librospe_db.intentos_login), (SELECT COUNT(*) FROM librospe_ms_usuarios.intentos_login), (SELECT COUNT(*) FROM librospe_db.intentos_login)= (SELECT COUNT(*) FROM librospe_ms_usuarios.intentos_login)
UNION ALL
SELECT 'bloqueos   ', 'bloqueos', 'bloqueos               ', (SELECT COUNT(*) FROM librospe_db.bloqueos), (SELECT COUNT(*) FROM librospe_ms_usuarios.bloqueos), (SELECT COUNT(*) FROM librospe_db.bloqueos)= (SELECT COUNT(*) FROM librospe_ms_usuarios.bloqueos)
UNION ALL
SELECT 'ruc_emp    ', 'ruc_empresas', 'ruc_empresas            ', (SELECT COUNT(*) FROM librospe_db.ruc_empresas), (SELECT COUNT(*) FROM librospe_ms_clientes.ruc_empresas), (SELECT COUNT(*) FROM librospe_db.ruc_empresas)= (SELECT COUNT(*) FROM librospe_ms_clientes.ruc_empresas)
UNION ALL
SELECT 'dptos      ', 'departamentos', 'departamentos          ', (SELECT COUNT(*) FROM librospe_db.departamentos), (SELECT COUNT(*) FROM librospe_ms_clientes.departamentos), (SELECT COUNT(*) FROM librospe_db.departamentos)= (SELECT COUNT(*) FROM librospe_ms_clientes.departamentos)
UNION ALL
SELECT 'prov       ', 'provincias', 'provincias             ', (SELECT COUNT(*) FROM librospe_db.provincias), (SELECT COUNT(*) FROM librospe_ms_clientes.provincias), (SELECT COUNT(*) FROM librospe_db.provincias)= (SELECT COUNT(*) FROM librospe_ms_clientes.provincias)
UNION ALL
SELECT 'distritos  ', 'distritos', 'distritos              ', (SELECT COUNT(*) FROM librospe_db.distritos), (SELECT COUNT(*) FROM librospe_ms_clientes.distritos), (SELECT COUNT(*) FROM librospe_db.distritos)= (SELECT COUNT(*) FROM librospe_ms_clientes.distritos);

-- 3) Prueba por PK: el mismo pedido existe en la principal y en ventas
SELECT '3) MISMO PEDIDO id=1 en ambas BDs:' AS prueba;
SELECT 'principal' AS bd, id, cliente_id, estado, total FROM librospe_db.pedidos WHERE id = 1
UNION ALL
SELECT 'ms_ventas', id, cliente_id, estado, total FROM librospe_ms_ventas.comercial_pedidos WHERE id = 1;