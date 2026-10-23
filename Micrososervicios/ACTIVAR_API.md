# Activación de la API Gateway JWT en producción

Estado: **todo subido y corriendo; falta 1 reinicio en el panel.**

## Qué está listo

| Paso | Estado |
|------|--------|
| Código: `www/app.py` con `API_GATEWAY=1`, `www/api_gateway_setup.py`, `gateways/`, `jwt_auth.py`, demo | subido (`deploy_api.ps1`) |
| `~/.env`: `API_GATEWAY=1` + `MS_INVENTARIO_URL/MS_VENTAS_URL/MS_USUARIOS_URL/MS_CLIENTES_URL = http://127.0.0.1:8001-8004` | listo (backup: `~/.env.bak-api-20261021-062744`) |
| 4 microservicios corriendo en `127.0.0.1:8001-8004` (bind local, no expuestos) | arriba y `/health` OK |
| Script idempotente `~/iniciar_servicios_api.sh` | instalado (`bash ~/iniciar_servicios_api.sh`) |
| Tienda actual (sin reiniciar) | viva, `/api/health` 200 |

## Único paso pendiente (panel Alwaysdata)

**Web > Sites > sitio de la tienda (librospe) > Restart.**

Tras el reinicio, `app.py` sirve a la vez:
- la tienda Jinja (igual que siempre),
- la API JSON en `/api/v1/*` con JWT (`/api/v1/health?profundo=1`),
- `/api/login` → demo del frontend.

## Verificación (post-restart)

1. `https://librospe.alwaysdata.net/` → 200 (tienda intacta).
2. `https://librospe.alwaysdata.net/api/health` → 200 (monitor heredado).
3. `https://librospe.alwaysdata.net/api/v1/health?profundo=1` → `"status": "OK"` y los 4 servicios `OK`.
4. `https://librospe.alwaysdata.net/static/api_demo/index.html` → login con un usuario real.

Si el paso 3 reporta servicios "caído/no alcanzable", la red del sitio no ve
`127.0.0.1` → plan B: crear los 4 servicios como sitios/command en el panel
con `MS_*_URL` apuntando a sus URLs internas.

## Persistencia (opcional, recomendado)

Los procesos `nohup` mueren si el servidor se reinicia. En **Jobs > Cron**
del panel, añadir (cada 5 minutos):

```bash
bash /home/librospe/iniciar_servicios_api.sh
```

El script es idempotente: solo lanza lo que no responda.

## Rollback

1. Editar `~/.env`: `API_GATEWAY=0` (backup: `~/.env.bak-api-20261021-062744`).
2. Reiniciar el sitio en el panel.
   La tienda queda exactamente como antes; los servicios pueden seguir corriendo.

## Seguridad

- Servicios bindeados a `127.0.0.1` (no expuestos a internet).
- `/api/v1/*` exige `Authorization: Bearer <JWT>` en toda mutación (CSRF acotado a `/api/v1`).
- Auditoría del gateway en `~/www/logs/auditoria_api.log` (JSON rotativo).
