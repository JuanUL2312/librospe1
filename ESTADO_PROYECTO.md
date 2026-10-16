# Estado del proyecto — traspaso entre PCs

Actualizado: 2026-10-16. Rama `main`. Último commit local: `998987f` ("mapa 1").

## Tareas

| Tarea | Estado |
|---|---|
| Categorías CRUD | ✅ cerrado y desplegado |
| Logo `LogoSalesiano.png` | ✅ 181 KB, **visible en producción** |
| Inventario con valuación | ✅ desplegado y verificado (admin ve la columna "Costo") |
| `/stock-bajo` | ✅ desplegado y verificado |
| Delivery con mapa (Leaflet + OpenStreetMap) | ✅ implementado y desplegado; `MAPA_TIENDA_LAT/LNG` ya configurados en `~/.env` |
| `/perfil` staff | ✅ existe y responde 200 |
| Bug 503 en `/api/comercial/validar-stock` (autollamada HTTP) | ✅ corregido en código y **desplegado**; falta reiniciar la app para que se cargue |
| Espejos y pedidos basura en `librospe_db` | ✅ limpiado (ver "Limpieza 2026-10-16") |
| Conf. uWSGI: `SECRET_KEY` duplicada y `static-map` erróneo | ⚠️ pendiente: `~/admin/config/uwsgi/1037421.conf` es de **root**; hay que editarlo en el panel |

Al retomar, en este orden:

1. **Panel alwaysdata → Web > Sites > librospe > Restart.** Es lo único que recarga
   el código nuevo y `~/.env` (uWSGI levanta bajo demanda y se apaga tras ~30 min
   de inactividad; ver "Estado de producción").
2. En la **configuración uWSGI del sitio** (panel): quitar la línea
   `env = SECRET_KEY=...` y corregir `static-map` a `/home/librospe/www/static`.
3. Verificar `GET /api/comercial/validar-stock/11/1` (con sesión admin) →
   200 en menos de 1 s (ya no 503 a los 5 s).

## Estado de producción (verificado 2026-10-16)

Servidor alwaysdata — `https://librospe.alwaysdata.net`

- `/api/health` → HTTP 200, version 3.0, los 4 microservicios `active`.
- Páginas públicas y de admin (con sesión) verificadas: `/productos`, `/inventario`,
  `/stock-bajo`, `/perfil`, `/categorias`, `/dashboard`, `/auditoria`,
  `/reportes/ventas_por_ubicacion`, `/delivery/mapa` → todas 200.
- Código desplegado byte a byte igual al repo (md5 de `app.py`, `wsgi.py`,
  `passenger_wsgi.py`, `ms_config.json` y los `microservicios/*.py`).
- Sincronización (cron horario) verificada: `~/sincronizar.sh` corre con rc=0 y
  todas las tablas quedan en `pendientes = 0`.

### Cómo se recarga la app en alwaysdata (importante)

El proxy de alwaysdata **arranca uWSGI bajo demanda** y lo detiene tras ~30 min
de inactividad (evidencia en `~/admin/logs/sites/YYYY/sites-YYYY-MM-DD.log`:
"Upstream stopped (reason: idle)"). Por lo tanto:

- `touch ~/www/tmp/restart.txt` **no** reinicia uWSGI (comprobado).
- Desde SSH **no** se puede reiniciar: los procesos viven en otro namespace
  (`ps aux` solo ve la propia sesión) y `sudo` está bloqueado
  ("no new privileges").
- **Única vía: panel de alwaysdata → Web > Sites > librospe > Restart.**
- Efecto colateral útil: si se dejan de hacer peticiones >30 min, el upstream se
  apaga solo y la siguiente petición lo arranca ya con el código nuevo.

### Conf. uWSGI del sitio (`~/admin/config/uwsgi/1037421.conf`)

Archivo propiedad de **root**, no editable por SSH/SFTP: hay que editarlo en el
panel. Dos problemas detectados:

- `env = SECRET_KEY=Librospe@2024#ClaveUltraSecreta!` — la clave está en claro en
  el conf y **tiene prioridad** sobre la de `~/.env` (la app usa
  `os.environ.setdefault`). Al quitarla, la app toma `SECRET_KEY` de `~/.env`
  (ya se dejó una clave aleatoria de 64 hex).
- `static-map = /static/=/home/librospe/home/librospe/www/static` — la ruta está
  duplicada; debe ser `/home/librospe/www/static`.

## Limpieza 2026-10-16 (producción)

Respaldo previo en `~/backups/2026-10-16-fixes/`:

- `librospe_db.sql` (dump completo) y `librospe_ms_ventas.sql` (dump completo).
- `1037421.conf.bak`, `env.bak` y los `*.py.bak` originales de `microservicios/`.

Cambios aplicados:

1. **Espejos eliminados en `librospe_db`** (el gateway ya lee de los binds):
   `comercial_pedidos`, `comercial_detalle_pedido`, `comercial_ventas`,
   `inventario_productos` (los otros 2 del script no existían). `librospe_db`
   pasó de 33 a 29 tablas. `sincronizar.sql` solo escribe en `librospe_ms_*`,
   así que el cron no se ve afectado.
2. **3 pedidos basura** (ids 21, 41, 43; carrito vacío, total 0.00, tipo recojo,
   sin detalle ni ventas ni pagos) borrados de `librospe_db.pedidos` y de
   `librospe_ms_ventas.comercial_pedidos` → quedan 72 en ambas.
3. `~/.env`: se añadieron `MAPA_TIENDA_LAT/LNG/NOMBRE`, `MAPA_USER_AGENT` y
   `SERVICE_TOKEN`. **Ojo:** los valores con espacios o paréntesis van **entre
   comillas**, porque `sincronizar.sh` hace `source ~/.env` con `set -e`
   (un valor sin comillas rompía el cron). `SECRET_KEY` pasó de un placeholder
   a una clave aleatoria de 64 hex.

### Bug 503 de `validar-stock` — arreglado en código

`routes_comercial._consultar_inventario` hace HTTP a `MS_INVENTARIO_URL`, que en
producción apunta a la propia app. Con `processes = 1`, el único worker quedaba
esperando su propia respuesta → 503 a los 5 s (timeout).

Fix (commit local pendiente de push): nueva función
`microservicios.es_llamada_a_si_mismo(url)` detecta cuándo la URL destino es esta
misma app (mismo host y puerto, tolerando el esquema http/https detrás del
proxy); en ese caso `_consultar_inventario` resuelve el stock **en proceso**
(reutilizando `routes_inventario.verificar_stock`) y responde en milisegundos.
Con servicios realmente separados (local en 8001-8004) se sigue usando
HTTP + `X-Service-Token`.

### Base `librospe_monolito`

Sigue existiendo pero el usuario MySQL `librospe` **no tiene privilegios** sobre
ella (`Access denied`), así que no se puede inspeccionar ni borrar desde aquí.

## Logo — comprimir antes de desplegar

`www/static/img/LogoSalesiano.png` pesa **1085 KB** (1254×1254 px) y ya está en
el repo. En los templates se usa a **44 px de alto** en los navbars
(`base.html`, `base_cliente.html`) y como imagen de tarjeta en la landing
(`index.html`), así que el tamaño original es innecesario.

Medición real con Pillow sobre el archivo del repo:

| Opción | Peso |
|---|---|
| original 1254 px | 1085 KB |
| 512 px, `optimize=True` | **181 KB** |

Reduce 6× sin pérdida visible a esa escala. Basta con redimensionar a 512 px
guardando como PNG; **no hay que cambiar el nombre ni los templates**.
Recomendado: hacerlo antes del deploy para no subir 1 MB por despliegue.

## Limpieza de datos demo

`Micrososervicios/limpiar_datos_demo.sql` — vacía clientes, pedidos y ventas,
deja solo `admin@mail.com` en `usuarios_sistema` y reinicia los `AUTO_INCREMENT`
en 1.

Tres cosas que hacen fácil equivocarse:

1. **El cron resucita los clientes.** Corre `0 * * * * sincronizar_completo.sh`.
   Para clientes, `librospe_ms_clientes` es la BD dueña y se copia hacia
   `librospe_db`. Hay que borrar en **las dos**, o una hora después vuelven.
2. **Arrastra el historial.** `pedidos` y `ventas` tienen FK hacia `clientes`;
   no se pueden vaciar los clientes sin borrarlos. El archivo incluye al final
   una variante "anular en lugar de borrar" si se quiere conservar las ventas.
3. **Salvaguarda anti lockout.** Si `admin@mail.com` no existe, el script no
   borra ningún usuario en vez de dejarlos sin acceso al sistema.

Ejecutar el **paso 0 primero** (debe devolver 1 fila con el admin) y hacer
respaldo antes.

## Entorno del PC anterior (este)

- ❌ **No hay `.env`**, solo `.env.example`. `app.py` lanza `RuntimeError` sin
  `SECRET_KEY`, así que la app no arranca localmente.
- ❌ **No hay clave SSH** (`~/.ssh/id_ed25519` no existe).
- ❌ **No hay Python en el PATH**, pero sí Anaconda en
  `C:\ProgramData\Anaconda3\python.exe` (Python 3.13.5, Pillow 11.1.0,
  SQLAlchemy 2.0.39, Flask 3.1.0, PyMySQL). `deploy.ps1` lo detecta por su glob.
- ✅ Red llega al servidor: MySQL 3306 y SSH 22 responden.

**En el otro PC hacen falta el `.env` y el acceso SSH/MySQL.**

## Notas sobre `deploy.ps1`

- Crea `.venv-live` e instala `paramiko` si faltan (usa Anaconda3 si no hay
  Python en el PATH).
- Genera la clave SSH si no existe, y si la clave aún no está autorizada en el
  servidor **pide la contraseña de alwaysdata de forma interactiva**
  (`Read-Host`). La primera vez no se puede ejecutar desatendido.
- Al terminar hay que **reiniciar la app a mano** en el panel de alwaysdata
  (Web > Sites > librospe > Restart): `tmp/restart.txt` no reinicia uWSGI.

## ESTRUCTURA de bases (para futuros borrados)

`librospe_db` (principal) + `librospe_ms_clientes`, `librospe_ms_usuarios`,
`librospe_ms_ventas`, `librospe_ms_inventario`.

Quién es dueño de qué (según `sincronizar.sql`):

- `clientes` → dueño `librospe_ms_clientes`, se copia hacia la principal.
- `usuarios_sistema` → dueño `librospe_db`, se copia hacia el microservicio.

FK que bloquean borrados en `librospe_db`:

| Tabla | Referencia |
|---|---|
| `pedidos` | `cliente_id` → `clientes` |
| `ventas` | `cliente_id` → `clientes`, `vendedor_id` → `usuarios_sistema` |
| `cajas` | `usuario_id` → `usuarios_sistema` |
| `intentos_login` | `cliente_id`, `usuario_sistema_id` |
| `bloqueos` | `cliente_id`, `usuario_sistema_id` |
| `auditoria` | `usuario_id` → `usuarios_sistema` |

Las tablas `comercial_pedidos` / `comercial_detalle_pedido` / `comercial_ventas`
en `librospe_ms_ventas` **no tienen FK**, pero guardan copia de los datos del
cliente (nombres, DNI, correo, dirección), así que también hay que limpiarlas
para no dejar datos personales sueltos.
