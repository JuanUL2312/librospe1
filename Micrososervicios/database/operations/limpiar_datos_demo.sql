-- LIMPIEZA DE DATOS DE DEMOSTRACION PARA EL ESQUEMA ACTUAL
-- Bases autorizadas: librospe_ms_clientes, librospe_ms_inventario,
-- librospe_ms_usuarios y librospe_ms_ventas.
-- Conserva catalogo, tablas de referencia y el usuario admin@mail.com.
-- Vaciar por completo un cliente/pedidos/ventas es irreversible: hacer backup.
-- Antes: detener temporalmente sitio/worker/cron; respaldar y purgar mensajes viejos del broker.
-- Si una sentencia falla: ejecutar ROLLBACK; SET FOREIGN_KEY_CHECKS = 1; y no continuar.
-- La base antigua librospe_db no se usa aqui (el usuario SQL no tiene permisos).

SET @admin := 'admin@mail.com';
SET @admin_id := (
    SELECT id FROM librospe_ms_usuarios.usuarios_sistema WHERE CONVERT(correo USING utf8mb4) COLLATE utf8mb4_general_ci = CONVERT(@admin USING utf8mb4) COLLATE utf8mb4_general_ci LIMIT 1
);

-- PREVUELO: confirmar que existe el admin. Debe devolver una fila.
SELECT id, correo, nombres, apellidos, rol, estado
FROM librospe_ms_usuarios.usuarios_sistema
WHERE CONVERT(correo USING utf8mb4) COLLATE utf8mb4_general_ci = CONVERT(@admin USING utf8mb4) COLLATE utf8mb4_general_ci;

-- Conteos antes de borrar.
SELECT 'clientes' AS tabla, COUNT(*) AS filas
FROM librospe_ms_clientes.clientes
UNION ALL SELECT 'pedidos', COUNT(*) FROM librospe_ms_ventas.pedidos
UNION ALL SELECT 'ventas', COUNT(*) FROM librospe_ms_ventas.ventas
UNION ALL SELECT 'pedidos_comerciales', COUNT(*) FROM librospe_ms_ventas.comercial_pedidos
UNION ALL SELECT 'ventas_comerciales', COUNT(*) FROM librospe_ms_ventas.comercial_ventas
UNION ALL SELECT 'usuarios_no_admin', COUNT(*)
    FROM librospe_ms_usuarios.usuarios_sistema WHERE CONVERT(correo USING utf8mb4) COLLATE utf8mb4_general_ci <> CONVERT(@admin USING utf8mb4) COLLATE utf8mb4_general_ci;

-- Si @admin_id es NULL, las condiciones impiden borrar cualquier fila.
-- Pausar procesos que escriben/consumen eventos antes de ejecutar esta seccion.
SET FOREIGN_KEY_CHECKS = 0;
START TRANSACTION;

-- Devolver cantidades que aun estaban reservadas/descontadas por pedidos
-- activos, antes de eliminar las reservas y los pedidos del demo.
SET @hay_conteos := (
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema = 'librospe_ms_inventario' AND table_name = 'conteos_stock'
);
SET @sql_borrar_conteos := IF(
    @hay_conteos > 0,
    'DELETE FROM librospe_ms_inventario.conteos_stock WHERE @admin_id IS NOT NULL',
    'SELECT 1'
);
PREPARE stmt_borrar_conteos FROM @sql_borrar_conteos;
EXECUTE stmt_borrar_conteos;
DEALLOCATE PREPARE stmt_borrar_conteos;

SET @hay_reservas := (
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema = 'librospe_ms_inventario' AND table_name = 'reservas_stock'
);
SET @sql_reponer := IF(
    @hay_reservas > 0,
    'UPDATE librospe_ms_inventario.inventario_productos AS p
     JOIN (SELECT producto_id, SUM(cantidad) AS unidades
           FROM librospe_ms_inventario.reservas_stock
           WHERE estado IN (''reservado'', ''confirmado'')
           GROUP BY producto_id) AS r ON r.producto_id = p.id
     SET p.cantidad = p.cantidad + r.unidades
     WHERE @admin_id IS NOT NULL',
    'SELECT 1'
);
PREPARE stmt_reponer FROM @sql_reponer;
EXECUTE stmt_reponer;
DEALLOCATE PREPARE stmt_reponer;

-- Detalles antes de cabeceras.
DELETE FROM librospe_ms_ventas.detalle_pedido WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_ventas.comercial_detalle_pedido WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_ventas.pedidos WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_ventas.comercial_pedidos WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_ventas.ventas WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_ventas.comercial_ventas WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_ventas.cajas WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_ventas.pos_ventas_idempotencia WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_ventas.eventos_pendientes WHERE @admin_id IS NOT NULL;

-- Copias locales usadas para JOIN dentro de cada microservicio.
DELETE FROM librospe_ms_ventas.clientes WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_inventario.ventas WHERE @admin_id IS NOT NULL;

-- Datos de cliente y registros de seguridad/auditoria del demo.
DELETE FROM librospe_ms_clientes.clientes WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_usuarios.auditoria WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_usuarios.intentos_login WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_usuarios.bloqueos WHERE @admin_id IS NOT NULL;
DELETE FROM librospe_ms_usuarios.usuarios_sistema
WHERE CONVERT(correo USING utf8mb4) COLLATE utf8mb4_general_ci <> CONVERT(@admin USING utf8mb4) COLLATE utf8mb4_general_ci
  AND @admin_id IS NOT NULL;
DELETE FROM librospe_ms_ventas.usuarios_sistema
WHERE CONVERT(correo USING utf8mb4) COLLATE utf8mb4_general_ci <> CONVERT(@admin USING utf8mb4) COLLATE utf8mb4_general_ci
  AND @admin_id IS NOT NULL;
DELETE FROM librospe_ms_inventario.usuarios_sistema
WHERE CONVERT(correo USING utf8mb4) COLLATE utf8mb4_general_ci <> CONVERT(@admin USING utf8mb4) COLLATE utf8mb4_general_ci
  AND @admin_id IS NOT NULL;

-- La tabla de reservas se crea al primer checkout; borrarla solo si existe.
SET @sql_borrar_reservas := IF(
    @hay_reservas > 0,
    'DELETE FROM librospe_ms_inventario.reservas_stock WHERE @admin_id IS NOT NULL',
    'SELECT 1'
);
PREPARE stmt_borrar_reservas FROM @sql_borrar_reservas;
EXECUTE stmt_borrar_reservas;
DEALLOCATE PREPARE stmt_borrar_reservas;

COMMIT;
SET FOREIGN_KEY_CHECKS = 1;

-- Reiniciar AUTO_INCREMENT en tablas que quedaron vacias.
-- Usuarios no se reinicia: se conserva el admin y su ID.
ALTER TABLE librospe_ms_clientes.clientes AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.detalle_pedido AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.comercial_detalle_pedido AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.pedidos AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.comercial_pedidos AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.ventas AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.comercial_ventas AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.cajas AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.clientes AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.eventos_pendientes AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_inventario.ventas AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_usuarios.auditoria AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_usuarios.intentos_login AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_usuarios.bloqueos AUTO_INCREMENT = 1;

SET @sql_reset_reservas := IF(
    @hay_reservas > 0,
    'ALTER TABLE librospe_ms_inventario.reservas_stock AUTO_INCREMENT = 1',
    'SELECT 1'
);
PREPARE stmt_reset_reservas FROM @sql_reset_reservas;
EXECUTE stmt_reset_reservas;
DEALLOCATE PREPARE stmt_reset_reservas;

SET @sql_reset_conteos := IF(
    @hay_conteos > 0,
    'ALTER TABLE librospe_ms_inventario.conteos_stock AUTO_INCREMENT = 1',
    'SELECT 1'
);
PREPARE stmt_reset_conteos FROM @sql_reset_conteos;
EXECUTE stmt_reset_conteos;
DEALLOCATE PREPARE stmt_reset_conteos;

-- Verificacion final. Las tablas operativas deben quedar en cero;
-- el usuario admin debe permanecer. El catalogo se conserva.
SELECT 'clientes' AS tabla, COUNT(*) AS filas FROM librospe_ms_clientes.clientes
UNION ALL SELECT 'pedidos', COUNT(*) FROM librospe_ms_ventas.pedidos
UNION ALL SELECT 'ventas', COUNT(*) FROM librospe_ms_ventas.ventas
UNION ALL SELECT 'pedidos_comerciales', COUNT(*) FROM librospe_ms_ventas.comercial_pedidos
UNION ALL SELECT 'ventas_comerciales', COUNT(*) FROM librospe_ms_ventas.comercial_ventas
;
SET @sql_verif_reservas := IF(
    @hay_reservas > 0,
    'SELECT ''reservas_activas'' AS tabla, COUNT(*) AS filas
     FROM librospe_ms_inventario.reservas_stock
     WHERE estado IN (''reservado'', ''confirmado'')',
    'SELECT ''reservas_stock'' AS tabla, 0 AS filas'
);
PREPARE stmt_verif_reservas FROM @sql_verif_reservas;
EXECUTE stmt_verif_reservas;
DEALLOCATE PREPARE stmt_verif_reservas;
SELECT id, correo, nombres, rol, estado
FROM librospe_ms_usuarios.usuarios_sistema WHERE CONVERT(correo USING utf8mb4) COLLATE utf8mb4_general_ci = CONVERT(@admin USING utf8mb4) COLLATE utf8mb4_general_ci;
