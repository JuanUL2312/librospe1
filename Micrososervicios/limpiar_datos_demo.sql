-- =====================================================================
--  LIMPIEZA DE DATOS DE DEMOSTRACION
--  Deja solo el usuario admin@mail.com en usuarios_sistema y vacia
--  clientes / pedidos / ventas, reiniciando los AUTO_INCREMENT en 1.
--
--  IMPORTANTE
--   1. Haz un RESPALDO antes de ejecutar.
--   2. Hay una sincronizacion por cron (0 * * * * sincronizar_completo.sh).
--      Para clientes, librospe_ms_clientes es la BD DUENA y se copia hacia
--      librospe_db. Por eso el script borra en AMBAS: si borras solo en
--      librospe_db, los clientes reaparecen a la hora siguiente.
--   3. Este script borra tambien el historial (pedidos/ventas) porque
--      tienen FK hacia clientes. Si quieres conservar las ventas, usa la
--      variante "ANULAR EN LUGAR DE BORRAR" al final del archivo.
--   4. Si @admin_id queda NULL (no existe ese correo), los DELETE de
--      usuarios NO se ejecutan: es una salvaguarda para no quedarse
--      sin acceso al sistema.
-- =====================================================================

SET FOREIGN_KEY_CHECKS = 0;
SET @admin    := 'admin@mail.com';
SET @admin_id := (SELECT id FROM librospe_db.usuarios_sistema WHERE correo = @admin);

-- ---------------------------------------------------------------------
-- 0. COMPROBACION OBLIGATORIA antes de seguir
--    Debe devolver 1 fila con el id del admin. Si devuelve 0 filas,
--    DETENTE: no continues, el admin no existe con ese correo.
-- ---------------------------------------------------------------------
SELECT id, correo, nombres, apellidos, rol, estado
FROM librospe_db.usuarios_sistema
WHERE correo = @admin;

SELECT 'clientes a borrar' AS vista, COUNT(*) AS filas
FROM librospe_db.clientes
UNION ALL SELECT 'usuarios a borrar', COUNT(*) FROM librospe_db.usuarios_sistema WHERE correo <> @admin;

-- ---------------------------------------------------------------------
-- 1. HISTORIAL que depende de clientes y usuarios (FK)
-- ---------------------------------------------------------------------
-- Detalle y cabecera de pedidos
DELETE FROM librospe_ms_ventas.comercial_detalle_pedido;
DELETE FROM librospe_db.detalle_pedido;
DELETE FROM librospe_ms_ventas.comercial_pedidos;
DELETE FROM librospe_db.pedidos;

-- Ventas: primero las que tienen cliente, luego las de otros vendedores
DELETE FROM librospe_db.ventas
 WHERE cliente_id IS NOT NULL
    OR (vendedor_id <> @admin_id AND @admin_id IS NOT NULL);
DELETE FROM librospe_ms_ventas.comercial_ventas
 WHERE cliente_id IS NOT NULL
    OR (vendedor_id <> @admin_id AND @admin_id IS NOT NULL);

-- Cajas, auditoria e intentos de login
DELETE FROM librospe_ms_usuarios.auditoria
 WHERE usuario_id IS NOT NULL AND usuario_id <> @admin_id AND @admin_id IS NOT NULL;
DELETE FROM librospe_db.auditoria
 WHERE usuario_id IS NOT NULL AND usuario_id <> @admin_id AND @admin_id IS NOT NULL;
DELETE FROM librospe_db.cajas
 WHERE usuario_id <> @admin_id AND @admin_id IS NOT NULL;
DELETE FROM librospe_db.intentos_login
 WHERE cliente_id IS NOT NULL
    OR (usuario_sistema_id <> @admin_id AND @admin_id IS NOT NULL);
DELETE FROM librospe_db.bloqueos
 WHERE cliente_id IS NOT NULL
    OR (usuario_sistema_id <> @admin_id AND @admin_id IS NOT NULL);
DELETE FROM librospe_ms_usuarios.intentos_login
 WHERE cliente_id IS NOT NULL
    OR (usuario_sistema_id IS NOT NULL AND usuario_sistema_id <> @admin_id AND @admin_id IS NOT NULL);
DELETE FROM librospe_ms_usuarios.bloqueos
 WHERE cliente_id IS NOT NULL
    OR (usuario_sistema_id IS NOT NULL AND usuario_sistema_id <> @admin_id AND @admin_id IS NOT NULL);

-- ---------------------------------------------------------------------
-- 2. CLIENTES  (las dos BDs: la duena y la principal)
-- ---------------------------------------------------------------------
DELETE FROM librospe_ms_clientes.clientes;
DELETE FROM librospe_db.clientes;

-- ---------------------------------------------------------------------
-- 3. USUARIOS DE SISTEMA  (solo queda admin@mail.com)
--    La condicion "@admin_id IS NOT NULL" evita borrar a todos si el
--    correo del admin no existe.
-- ---------------------------------------------------------------------
DELETE FROM librospe_ms_usuarios.usuarios_sistema
 WHERE correo <> @admin AND @admin_id IS NOT NULL;
DELETE FROM librospe_db.usuarios_sistema
 WHERE correo <> @admin AND @admin_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 4. REINICIAR AUTO_INCREMENT en 1
--    (solo surte efecto si la tabla quedo vacia; por eso va al final)
-- ---------------------------------------------------------------------
ALTER TABLE librospe_ms_clientes.clientes              AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.clientes                       AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.pedidos                        AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.detalle_pedido                 AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.comercial_pedidos       AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.comercial_detalle_pedido AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.ventas                         AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.comercial_ventas        AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.cajas                          AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.auditoria                      AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_usuarios.auditoria             AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.intentos_login                 AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.bloqueos                       AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_usuarios.usuarios_sistema      AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.usuarios_sistema               AUTO_INCREMENT = 1;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 5. VERIFICACION (clientes/pedidos/ventas deben dar 0;
--    usuarios_sistema debe dar 1)
-- ---------------------------------------------------------------------
SELECT 'clientes'      AS tabla, COUNT(*) AS filas FROM librospe_db.clientes
UNION ALL SELECT 'ms_clientes',   COUNT(*) FROM librospe_ms_clientes.clientes
UNION ALL SELECT 'pedidos',       COUNT(*) FROM librospe_db.pedidos
UNION ALL SELECT 'detalle_pedido',COUNT(*) FROM librospe_db.detalle_pedido
UNION ALL SELECT 'ventas',        COUNT(*) FROM librospe_db.ventas
UNION ALL SELECT 'cajas',         COUNT(*) FROM librospe_db.cajas
UNION ALL SELECT 'usuarios',      COUNT(*) FROM librospe_db.usuarios_sistema
UNION ALL SELECT 'ms_usuarios',   COUNT(*) FROM librospe_ms_usuarios.usuarios_sistema;

SELECT id, correo, nombres, rol, estado FROM librospe_db.usuarios_sistema;

-- ---------------------------------------------------------------------
-- VARIANTE: si prefieres CONSERVAR el historial de ventas
-- Reemplaza el bloque de ventas del paso 1 por esto.
-- ventas.cliente_id es NULLABLE, pero pedidos.cliente_id es NOT NULL,
-- asi que los pedidos se borran de todas formas:
--
--   DELETE FROM librospe_db.detalle_pedido;
--   DELETE FROM librospe_db.pedidos;
--   DELETE FROM librospe_ms_ventas.comercial_detalle_pedido;
--   DELETE FROM librospe_ms_ventas.comercial_pedidos;
--   UPDATE librospe_db.ventas SET cliente_id = NULL WHERE cliente_id IS NOT NULL;
--   UPDATE librospe_ms_ventas.comercial_ventas SET cliente_id = NULL WHERE cliente_id IS NOT NULL;
--   UPDATE librospe_db.ventas SET vendedor_id = @admin_id WHERE vendedor_id <> @admin_id;
--   UPDATE librospe_ms_ventas.comercial_ventas SET vendedor_id = @admin_id WHERE vendedor_id <> @admin_id;
--   DELETE FROM librospe_db.ventas WHERE cliente_id IS NULL;
--
-- ...y en el paso 4 omite el ALTER de ventas/comercial_ventas para no
-- reiniciar el historial de ventas.
-- ---------------------------------------------------------------------
