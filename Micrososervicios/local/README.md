# Archivos de desarrollo local

Esta carpeta agrupa utilidades ejecutadas desde la computadora del desarrollador. No se copia como parte del despliegue web de Alwaysdata.

- `windows/`: iniciadores de desarrollo y reinicio local.
- `admin/`: herramientas locales para desplegar, migrar, diagnosticar y demostrar el sistema; `restart.sh`, `check_restart.sh` y `verificar_sincronizacion.sh` usan rutas relativas al proyecto local. Algunas se conectan a Alwaysdata cuando se ejecutan.
- `dev/`: pytest y dependencias de desarrollo usadas tambi?n por CI.
- `database-backups/`: volcados locales; pueden contener informaci?n privada.

Los scripts de servicios y tareas programadas que se ejecutan en Alwaysdata permanecen en la ra?z del proyecto.
