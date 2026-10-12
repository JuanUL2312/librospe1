# Estado del proyecto — traspaso entre PCs

Actualizado: 2026-10-12. Rama `main`. Último commit: `fed88f3`.

## Tareas

| Tarea | Estado |
|---|---|
| Paso 1 — Categorías CRUD | ✅ cerrado y probado (`fa0416f`), desplegado en producción |
| Logo `LogoSalesiano.png` | ✅ comprimido a 181 KB y **visible en producción** |
| Paso 2 — Inventario con valuación | ⚠️ código subido al servidor, **falta reiniciar la app** (panel alwaysdata) |
| Paso 3 — `/stock-bajo` | ⚠️ implementado y probado en local, subido al servidor, **falta reiniciar** y probar E2E |
| Limpieza de datos demo | ✅ script listo (`Micrososervicios/limpiar_datos_demo.sql`), sin ejecutar |
| Delivery con mapa para dirección | ❌ sin empezar (decidido: Leaflet + OpenStreetMap) |
| Paso 4 — `/perfil` staff | ❌ sin empezar (la ruta no existe; el personal solo tiene `/cambiar_clave`) |

Al retomar, en este orden:

1. `deploy.ps1` → deploy de `fed88f3` (logo + inventario).
2. Verificar logo (navbar admin/cliente + landing) y `/inventario`:
   admin ve la columna de costo, vendedor no.
3. Pruebas E2E.
4. Commit.

## Estado de producción (verificado 2026-10-12 22:33)

Servidor alwaysdata — `https://librospe.alwaysdata.net`

- `/api/health` → HTTP 200, version 3.0, los 4 microservicios `active`.
- Deploy ejecutado a las 22:32: código subido con SFTP + rsync a `~/www/`.
- `fa0416f` (categorías) desplegado: `/categorias` responde 302 al login.
- El **logo ya está vivo**: `/static/img/LogoSalesiano.png` → HTTP 200,
  185560 bytes. Los estáticos los sirve Apache directo, sin depender del
  reinicio del proceso Python.

### PENDIENTE: reiniciar la app (bloquea a `/inventario` y `/stock-bajo`)

| Ruta | Estado |
|---|---|
| `/inventario` | 404 — el proceso sigue con el código viejo |
| `/stock-bajo` | 404 — ídem |

`touch ~/www/tmp/restart.txt` **no reinicia** el uWSGI en alwaysdata
(comprobado: se recreó el archivo a las 22:33 y las rutas siguen en 404).
Desde SSH tampoco: `ps aux` no muestra los procesos de Apache/Passenger
porque corren fuera del namespace del usuario.

Única vía: **panel de alwaysdata → Web > Sites > librospe > Restart**.

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
