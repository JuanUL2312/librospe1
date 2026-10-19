# Estado del proyecto — traspaso entre PCs

Actualizado: 2026-10-20. Rama `main`.

## Arquitectura actual (microservicios)

| Componente | Dónde | Puerto | Base de datos |
|---|---|---|---|
| **Gateway** (tienda completa, 136 rutas) | `www/` | 8000 |_bind por modelo_ |
| Inventario | `servicio-inventario/` | 8001 | `librospe_ms_inventario` |
| Ventas | `servicio-ventas/` | 8002 | `librospe_ms_ventas` |
| Usuarios | `servicio-usuarios/` | 8003 | `librospe_ms_usuarios` |
| Clientes | `servicio-clientes/` | 8004 | `librospe_ms_clientes` |
| **Agente de mensajes** | RabbitMQ (alwaysdata) | 5672 | vhost `librospe_ra` |

> **`librospe_db` (la base central) fue ELIMINADA.** Cada tabla vive en la
> base de su microservicio. El gateway sigue siendo un solo proceso uWSGI
> (alwaysdata) y reparte el trabajo por *bind* de SQLAlchemy:
> cada modelo declara su `__bind_key__` y el SQL crudo se enruta solo a la
> base correcta (`SesionEnrutada` en `www/app.py`).

### Copias locales (por qué existen)

MySQL no puede unir tablas de bases distintas. Para los JOIN que el panel
necesita (venta → producto → proveedor, pedido → cliente), cada servicio
guarda en **su propia base** una copia de las claves foraneas que usa:

| Copia | Dueño |
|---|---|
| `ms_ventas.productos / categorias / proveedores` | `ms_inventario` |
| `ms_ventas.usuarios_sistema / roles` | `ms_usuarios` |
| `ms_ventas.clientes` | `ms_clientes` |
| `ms_inventario.usuarios_sistema` | `ms_usuarios` |
| `ms_inventario.ventas` | `ms_ventas` |

Se mantienen al día con el **agente de mensajes (RabbitMQ)** en tiempo real y,
como red de seguridad, con el cron horario `~/sincronizar_completo.sh`
(que usa `~/sincronizar_copias.sql`).

En el código, los modelos espejo son `ProductoEnVentas`, `UsuarioEnVentas`,
`ClienteEnVentas`, `VentaEnInventario`, `UsuarioEnInventario`.

## Tareas

| Tarea | Estado |
|---|---|
| Migración de `librospe_db` a los 4 microservicios | ✅ hecho y verificado |
| `librospe_db` eliminada | ✅ (panel alwaysdata) |
| Modelos con `__bind_key__` + enrutado del SQL crudo | ✅ |
| Modelos espejo (copias locales) | ✅ |
| Agente de mensajes RabbitMQ | ✅ desplegado y probado E2E |
| Reportes de "no recibido" (badge, contador, filtro) | ✅ |
| SMS al cliente (comprobante por mensaje de texto) | ⚠️ falta `SMS_PROVIDER` en el `.env` |
| Mapas por distrito + detección del distrito al marcar el pin | ✅ |
| **Reiniciar la app** (panel) para que corra el consumidor de eventos | ⏳ pendiente |
| Cron `*/10 * * * * /home/librospe/procesar_eventos.sh` (panel) | ⏳ pendiente |
| `SECRET_KEY` fuerte en el `.env` + quitarlo del `uwsgi.conf` | ⏳ pendiente (ver Seguridad) |
| Cambiar la contraseña de SSH/MySQL/RabbitMQ | ⏳ pendiente (ver Seguridad) |

## Estado de producción (verificado 2026-10-20)

Servidor alwaysdata — `https://librospe.alwaysdata.net`

- `/api/health` → HTTP 200, los 4 microservicios `active`.
- 16/16 páginas del panel verificadas con 200 (dashboard, productos, ventas,
  pedidos, inventario, stock-bajo, caja, auditoría, usuarios, microservicios,
  reportes, mapa de delivery, comprobante, detalle de pedido, catálogo, carrito).
- **Escrituras verificadas**: producto → `ms_inventario`, cliente →
  `ms_clientes`, venta + pedido → `ms_ventas` (con stock descontado en
  inventario). `librospe_db` no recibe ni una fila.
- **RabbitMQ**: `amqp://librospe:<clave>@rabbitmq-librospe.alwaysdata.net:5672/librospe_ra`
  → evento `producto.actualizado` publicado, consumido por el gateway y
  copias locales al día; las 4 colas quedan en 0.
- Cron horario de sincronización: `pendientes = 0` en las 8 copias.

## ⏳ Pendiente inmediato: reiniciar la app

El proceso uWSGI en memoria puede tener el código anterior. Se reinicia desde
el panel: **Web > Sites > librospe > Restart**.

> `touch ~/www/tmp/restart.txt` **no** reinicia uWSGI (comprobado). El proxy
> de alwaysdata manda SIGHUP en algunos momentos, pero no es fiable. La
> única vía es el panel.

## Seguridad (pendiente)

1. **El `SECRET_KEY` real está en el `uwsgi.conf`** (propiedad de root, no
   editable por SSH):
   `env = SECRET_KEY=Librospe@2024#ClaveUltraSecreta!`
   Esa línea **tiene prioridad** sobre el `.env` (la app usa
   `os.environ.setdefault`). Para cambiarlo:
   - primero agregar al `.env`: `SECRET_KEY=<64 hex aleatorios>`;
   - luego quitar la línea `env = SECRET_KEY=...` del `uwsgi.conf` (panel).
2. La contraseña de **SSH, MySQL y RabbitMQ es la misma** y está escrita en
   claro en este repositorio de trabajo: **cámbiala en los tres sitios**.
3. `~/sincronizar_completo.sh` tenía la clave escrita en claro → ya se
   corrigió (lee `DB_PASSWORD` del `.env`).
4. El `.env` **nunca** debe subirse a git (está en `.gitignore`).

## Requisitos del entorno

- Python 3.13, `pip install -r Micrososervicios/requirements.txt`
- Pruebas: `pip install -r Micrososervicios/requirements-dev.txt` y
  `python -m pytest Micrososervicios/tests -q`
  (las pruebas que necesitan MySQL usan las variables `TEST_DB_*`).
- CI: `.github/workflows/ci.yml` (pruebas + sintaxis + `docker compose config`).

## Cómo se recarga la app en alwaysdata

- `alwaysdata` es hosting compartido: **un solo proceso uWSGI** por sitio.
- El proxy inicia el upstream bajo demanda y lo detiene tras ~30 min de
  inactividad. Si se deja de hacer peticiones >30 min, el siguiente arranque
  ya carga el código nuevo.
- Despliegue: `Micrososervicios/deploy.ps1` (SFTP por clave SSH; la clave
  ya está autorizada en el servidor desde 2026-10-19) o `rsync` manual.

## Comandos útiles en el servidor

```bash
tail -f ~/admin/logs/uwsgi/1037421.log    # log de la app (print)
tail -f ~/admin/logs/sites/2026/*.log     # log del proxy (SIGHUP, idle)
tail -f ~/admin/logs/http/2026/*.log       # accesos
tail -f ~/sincronizacion.log              # sincronizacion de copias
bash ~/sincronizar_completo.sh            # forzar la sincronizacion
bash ~/procesar_eventos.sh                # reintentar el outbox
```

## Estructura de bases (dueño de cada tabla)

- `librospe_ms_inventario`: productos, categorias, proveedores, conteos_stock
  (+ copias: usuarios_sistema, ventas)
- `librospe_ms_ventas`: ventas, pedidos, detalle_pedido, cajas, cupones,
  pagos, ajustes_pago, resenas (+ copias: productos, categorias, proveedores,
  usuarios_sistema, roles, clientes)
- `librospe_ms_usuarios`: usuarios_sistema, roles, permisos, rol_permisos,
  intentos_login, bloqueos, auditoria, configuracion_sistema,
  cambios_configuracion
- `librospe_ms_clientes`: clientes, ruc_empresas, departamentos, provincias,
  distritos

## Cosas que quedaron a medias en la sesión anterior

- `Monilitico/` y `Monilitico.zip` (el monolito viejo) siguen en el repo.
- Los 5 `.temp_*.py` (scripts de un solo uso) siguen versionados.
- `arquitectura-ms.html` / `arquitectura-ms.archify.json` (el diagrama) se
  regeneraron con la arquitectura de microservicios.
