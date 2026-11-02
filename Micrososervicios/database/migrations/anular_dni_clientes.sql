-- =====================================================================
--  ANULAR EL DNI DE LOS CLIENTES  (deja dni = NULL)
--
--  IMPORTANTE: hay que tocar LAS DOS bases
--  En sincronizar.sql:556 el microservicio es el DUENO de clientes y hace
--      UPDATE librospe_db.clientes ... SET c.dni = mc.dni ...
--  es decir, la principal se REESCRIBE desde librospe_ms_clientes cada hora
--  (cron 0 * * * *). Si anulas el dni solo en librospe_db, en menos de una
--  hora los DNI vuelven tal cual. Por eso el orden es: duena primero.
--
--  NO AFECTA A LA ESTRUCTURA: dni no tiene indice UNIQUE (el unico UNIQUE
--  de clientes es uq_correo), asi que admite NULL en varias filas sin
--  conflicto. No hay que tocar la FK ni el AUTO_INCREMENT.
--
--  HAZ UN RESPALDO ANTES.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. COMPROBACION: cuantos DNI se van a anular y donde siguen guardados
-- ---------------------------------------------------------------------
SELECT 'librospe_db (principal)'      AS base, COUNT(*) AS con_dni
FROM librospe_db.clientes             WHERE dni IS NOT NULL
UNION ALL
SELECT 'librospe_ms_clientes (duena)', COUNT(*)
FROM librospe_ms_clientes.clientes    WHERE dni IS NOT NULL
UNION ALL
SELECT 'ventas (copia en historial)',  COUNT(*)
FROM librospe_db.ventas               WHERE cliente_documento IS NOT NULL
UNION ALL
SELECT 'comercial_ventas (copia MS)',  COUNT(*)
FROM librospe_ms_ventas.comercial_ventas WHERE cliente_documento IS NOT NULL;

-- ---------------------------------------------------------------------
-- 1. ANULAR EL DNI  (BD duena primero, luego el espejo de la principal)
-- ---------------------------------------------------------------------
UPDATE librospe_ms_clientes.clientes SET dni = NULL WHERE dni IS NOT NULL;
UPDATE librospe_db.clientes          SET dni = NULL WHERE dni IS NOT NULL;

SET FOREIGN_KEY_CHECKS = 1;   -- no hubo FK afectadas, se restablece por si acaso

-- ---------------------------------------------------------------------
-- 2. VERIFICACION: ambas bases deben dar 0
-- ---------------------------------------------------------------------
SELECT 'librospe_db (principal)'      AS base, COUNT(*) AS con_dni
FROM librospe_db.clientes             WHERE dni IS NOT NULL
UNION ALL
SELECT 'librospe_ms_clientes (duena)', COUNT(*)
FROM librospe_ms_clientes.clientes    WHERE dni IS NOT NULL;

SELECT id, nombres, apellidos, IFNULL(dni, 'NULL') AS dni, correo
FROM librospe_db.clientes
ORDER BY id;

-- =====================================================================
--  OPCIONAL (descomentar solo si tambien quieres borrar el historial)
-- =====================================================================
--
-- El DNI no vive solo en clientes: queda COPIADO en el historial de ventas.
-- Anularlo en clientes deja los numeros ahi.
--
-- 3. Anular tambien la copia del historial:
--
-- UPDATE librospe_db.ventas                SET cliente_documento = NULL WHERE cliente_documento IS NOT NULL;
-- UPDATE librospe_ms_ventas.comercial_ventas SET cliente_documento = NULL WHERE cliente_documento IS NOT NULL;
--
-- Ojo: con esto la venta deja de poder associarse al cliente por documento
-- (app.py:4249, 2882 y 3309 buscan por dni/ruc/ce).
--
-- ---------------------------------------------------------------------
-- 4. Si quieres limpiar tambien CE y RUC (no solo DNI):
--
-- UPDATE librospe_ms_clientes.clientes SET ce = NULL, ruc = NULL WHERE ce IS NOT NULL OR ruc IS NOT NULL;
-- UPDATE librospe_db.clientes          SET ce = NULL, ruc = NULL WHERE ce IS NOT NULL OR ruc IS NOT NULL;
-- ---------------------------------------------------------------------
