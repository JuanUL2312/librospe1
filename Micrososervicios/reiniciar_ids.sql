-- =====================================================================
--  REINICIAR LOS AUTO_INCREMENT EN 1  (para que los ids vuelvan a empezar)
--
--  REGLA DE ORO: primero DELETE, despues ALTER.
--  En InnoDB, ALTER TABLE ... AUTO_INCREMENT = 1 solo surte efecto si la
--  tabla quedo VACIA. Si todavia hay filas, el motor usa max(id)+1 y el
--  ALTER se ignora en silencio (no da error, no avisa).
--
--  POR QUE HAY QUE HACERLO EN LAS DOS BASES DE CLIENTES
--  Los clientes viven duplicados y el cron sincroniza por id:
--      sincronizar.sql:524  INSERT IGNORE librospe_ms_clientes.clientes ... JOIN por id
--      sincronizar.sql:540  INSERT IGNORE librospe_db.clientes          ... JOIN por id
--  Si reseteas el AUTO_INCREMENT de una sola base, el proximo cliente
--  insertado choca en id contra una fila que ya existe en la OTRA base.
--  Como es INSERT IGNORE, no da error: la fila simplemente se pierde o se
--  mezcla con la que ya estaba. Se resetean las dos, sin intervenedientes.
--
--  NO USES TRUNCATE
--  TRUNCATE si reinicia el AUTO_INCREMENT, pero MySQL lo rechaza con
--  error 1701 en tablas referenciadas por una FK. librospe_db.clientes la
--  referencian pedidos y ventas, asi que TRUNCATE falla. Por eso
--  DELETE + ALTER.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. DIAGNOSTICO: que hay antes y cual seria el siguiente id
-- ---------------------------------------------------------------------
SELECT TABLE_SCHEMA AS base, TABLE_NAME AS tabla,
       TABLE_ROWS AS filas_aprox, AUTO_INCREMENT AS siguiente_id
FROM information_schema.TABLES
WHERE TABLE_SCHEMA IN ('librospe_db','librospe_ms_clientes','librospe_ms_usuarios','librospe_ms_ventas')
  AND TABLE_NAME IN ('clientes','pedidos','detalle_pedido','ventas','cajas',
                     'intentos_login','bloqueos','usuarios_sistema',
                     'comercial_pedidos','comercial_detalle_pedido','comercial_ventas')
ORDER BY TABLE_SCHEMA, TABLE_NAME;

-- El siguiente id REAL, no el estimado (TABLE_ROWS es aproximado):
SELECT 'clientes ms (duena)' AS tabla, IFNULL(MAX(id), 0) AS max_id, COUNT(*) AS filas
FROM librospe_ms_clientes.clientes
UNION ALL SELECT 'clientes principal', IFNULL(MAX(id), 0), COUNT(*) FROM librospe_db.clientes;

-- ---------------------------------------------------------------------
-- 2. BORRAR primero (si la tabla no quedo vacia, el ALTER no hace nada)
--    Ajusta el WHERE si quieres conservar clientes:
--      DELETE FROM librospe_db.clientes;                    -- borra todos
--      DELETE FROM librospe_db.clientes WHERE id > 50;     -- conserva los 50 primeros
-- ---------------------------------------------------------------------
DELETE FROM librospe_ms_clientes.clientes;
DELETE FROM librospe_db.clientes;

-- ---------------------------------------------------------------------
-- 3. RESETEAR los AUTO_INCREMENT
--    Orden: duena primero, luego espejo. Sin clocks ni inserts en medio.
-- ---------------------------------------------------------------------
ALTER TABLE librospe_ms_clientes.clientes              AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.clientes                       AUTO_INCREMENT = 1;

-- Tablas de historial (solo si tambien las vaciaste)
ALTER TABLE librospe_db.pedidos                        AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.detalle_pedido                 AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.ventas                         AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.comercial_pedidos       AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.comercial_detalle_pedido AUTO_INCREMENT = 1;
ALTER TABLE librospe_ms_ventas.comercial_ventas        AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.cajas                          AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.intentos_login                 AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.bloqueos                       AUTO_INCREMENT = 1;

-- Usuarios de sistema: solo si quedo SOLO el admin.
-- Si el admin ya tiene id 1, el siguiente usuario sera 2, no 1: es correcto.
ALTER TABLE librospe_ms_usuarios.usuarios_sistema      AUTO_INCREMENT = 1;
ALTER TABLE librospe_db.usuarios_sistema               AUTO_INCREMENT = 1;

-- ---------------------------------------------------------------------
-- 4. VERIFICACION: clientes debe dar siguiente_id = 1
-- ---------------------------------------------------------------------
SELECT TABLE_SCHEMA AS base, TABLE_NAME AS tabla, AUTO_INCREMENT AS siguiente_id
FROM information_schema.TABLES
WHERE (TABLE_SCHEMA = 'librospe_db'       AND TABLE_NAME = 'clientes')
   OR (TABLE_SCHEMA = 'librospe_ms_clientes' AND TABLE_NAME = 'clientes');

-- =====================================================================
--  SI EL VERIFICACION NO DA 1, revisa esto:
--
--  a) "ALTER no hizo nada": quedaron filas. Corregido con el DELETE del
--     paso 2. En InnoDB el AUTO_INCREMENT nunca baja de max(id)+1.
--
--  b) "Vuelve a 15 a la media hora": el cron reinserto filas desde el
--     espejo. Falto borrar en una de las dos bases, o se reseteo solo una.
--     Verifica que AMBAS den 0 filas antes del ALTER.
--
--  c) MySQL 8 persiste el contador en el Tablespace, asi que un simple
--     DELETE ya lo reinicia solo en algunos casos; el ALTER explicito
--     sigue siendo lo seguro.
-- =====================================================================
