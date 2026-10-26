# Activar las APIs de LibrosPE en Alwaysdata

## Estado

El sitio web y sus consultas SQL pueden responder aunque el monitor muestre `DEGRADADO`. Ese estado indica que los cuatro procesos HTTP de microservicios no responden. Un `tmp/restart.txt` reinicia el sitio WSGI, pero no inicia esos procesos.

## Desplegar el codigo

Desde `Micrososervicios` en PowerShell ejecuta:

```powershell
.\deploy_api.ps1
```

Este script sube `www/` y los cuatro directorios de servicio, e instala Gunicorn en `~/www/venv`. Despues registra los procesos administrados indicados abajo. No uses `nohup` ni tareas programadas para dejarlos corriendo.

## Servicios administrados

En **Advanced > Services**, agrega los servicios con estos comandos en primer plano:

| Servicio | Comando |
|---|---|
| inventario | `cd /home/librospe/servicio-inventario && /home/librospe/www/venv/bin/python -m gunicorn --bind ::8300 --workers 1 --threads 2 --timeout 45 app:app` |
| ventas | `cd /home/librospe/servicio-ventas && /home/librospe/www/venv/bin/python -m gunicorn --bind ::8301 --workers 1 --threads 2 --timeout 45 app:app` |
| usuarios | `cd /home/librospe/servicio-usuarios && /home/librospe/www/venv/bin/python -m gunicorn --bind ::8302 --workers 1 --threads 2 --timeout 45 app:app` |
| clientes | `cd /home/librospe/servicio-clientes && /home/librospe/www/venv/bin/python -m gunicorn --bind ::8303 --workers 1 --threads 2 --timeout 45 app:app` |

Los servicios deben cargar las mismas credenciales de base de datos y `SERVICE_TOKEN` desde `/home/librospe/.env`. No copies secretos en los comandos del panel. Toda ruta de API exige el token; `/health` es publico para permitir el monitoreo.

## URLs del Gateway

Configura en las variables de entorno del sitio Gateway:

```text
MS_INVENTARIO_URL=http://services-librospe.alwaysdata.net:8300
MS_VENTAS_URL=http://services-librospe.alwaysdata.net:8301
MS_USUARIOS_URL=http://services-librospe.alwaysdata.net:8302
MS_CLIENTES_URL=http://services-librospe.alwaysdata.net:8303
```

Configura tambien `MS_INVENTARIO_URL` del servicio ventas con la URL del servicio inventario. Mant?n iguales `SERVICE_TOKEN` del sitio y de los procesos.

## Verificacion

Reinicia el sitio en **Web > Sites > Restart** y consulta:

- `https://librospe.alwaysdata.net/api/health`: las cuatro claves de `http_servicios` deben indicar `OK`.
- `https://librospe.alwaysdata.net/api/productos/recomendados`: debe devolver HTTP 200.

Si health sigue degradado, revisa **Advanced > Services** y los logs de servicio; no ocultes el estado ni lo cambies manualmente a `OK`.

## Seguridad

Los puertos de Alwaysdata Services son accesibles externamente. Las rutas privadas validan `X-Service-Token`; mant?n un token aleatorio y distinto de las claves de desarrollo. El listener mostrado usa HTTP; para trafico de produccion con datos sensibles, confirma/configura TLS para esos endpoints antes de utilizarlos con clientes reales.
