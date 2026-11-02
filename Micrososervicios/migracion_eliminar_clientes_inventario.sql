-- Retira la antigua copia de clientes que estaba en inventario.
-- La tabla propietaria es librospe_ms_clientes.clientes. El Gateway y los
-- microservicios resuelven los datos del cliente por su bind/API.
--
-- Guardia: aborta si quedan filas o si otra tabla tiene una FK hacia esta.
-- Se puede volver a ejecutar: si la tabla ya no existe, no hace nada.
DELIMITER //
DROP PROCEDURE IF EXISTS migracion_eliminar_clientes_inventario//
CREATE PROCEDURE migracion_eliminar_clientes_inventario()
BEGIN
    DECLARE existe INT DEFAULT 0;
    DECLARE filas INT DEFAULT 0;
    DECLARE referencias INT DEFAULT 0;

    SELECT COUNT(*) INTO existe
      FROM information_schema.tables
     WHERE table_schema = 'librospe_ms_inventario'
       AND table_name = 'clientes';

    IF existe > 0 THEN
        SELECT COUNT(*) INTO filas
          FROM librospe_ms_inventario.clientes;

        SELECT COUNT(*) INTO referencias
          FROM information_schema.key_column_usage
         WHERE referenced_table_schema = 'librospe_ms_inventario'
           AND referenced_table_name = 'clientes';

        IF filas <> 0 OR referencias <> 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'No se elimina inventario.clientes: hay filas o claves foraneas';
        END IF;

        DROP TABLE librospe_ms_inventario.clientes;
    END IF;
END//
CALL migracion_eliminar_clientes_inventario()//
DROP PROCEDURE migracion_eliminar_clientes_inventario//
DELIMITER ;
