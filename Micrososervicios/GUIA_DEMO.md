# Guía de demostración: Microservicios de LibrosPE

Presentación ante docente. Objetivo: mostrar que la aplicación se divide en **dominios de negocio independientes** (microservicios), **cada uno con SU PROPIA base de datos**, conectados entre sí por HTTP.

---

## 1. Resumen para presentar (2 min)

| Microservicio | Prefijo | Responsabilidad | Su base de datos |
|---|---|---|---|
| **ventas** | `/api/comercial` | Pedidos y ventas | `librospe_ms_ventas` (`comercial_pedidos*`) |
| **inventario** | `/api/inventario` | Productos y stock | `librospe_ms_inventario` (`inventario_productos*`) |
| **usuarios** | `/api/usuarios` | Usuarios y roles | `librospe_ms_usuarios` (`usuarios_sistema`, `roles`) |
| **clientes** | `/api/clientes` | Clientes registrados | `librospe_ms_clientes` (`clientes`) |
| **monitor** | `/api` | Health check de las 4 BDs | `information_schema` |

**Arquitectura:** cada microservicio es un *blueprint Flask* independiente en `www/microservicios/`, con su propio `url_prefix` y su propio **schema de MySQL** (bind de SQLAlchemy). Un servicio **jamás** lee la BD de otro: la comunicación es **HTTP con token interno** `X-Service-Token`. Las dependencias compartidas (`db` y `login_required`) se inyectan en `register_microservicios()` (www/microservicios/__init__.py:59).

**Endpoints:**
- `GET  /api/health` → estado de los servicios y de cada BD (público)
- `GET  /api/comercial/pedidos` → pedidos (BD ventas)
- `GET  /api/comercial/pedidos/<id>` → pedido + detalles
- `PUT  /api/comercial/pedidos/<id>/estado` → cambiar estado (solo admin)
- `GET  /api/comercial/ventas` → ventas
- `GET  /api/comercial/validar-stock/<id>/<cant>` → **integración**: ventas consulta a inventario por HTTP
- `GET  /api/inventario/productos` → productos (BD inventario)
- `GET  /api/inventario/productos/<id>` → producto
- `PUT  /api/inventario/stock/<id>` → actualizar stock (solo admin)
- `GET  /api/inventario/stock/bajo/<min>` → stock bajo
- `GET  /api/inventario/verificar-stock/<id>/<cant>` → validación de stock
- `GET  /api/usuarios` → usuarios del sistema (BD usuarios)
- `GET  /api/usuarios/roles` → roles
- `GET  /api/clientes` → clientes (BD clientes)
- `GET  /api/clientes/ubicacion` → resumen por ubicación

---

## 2. Guion de demostración (10-15 min)

### Paso 0 — Preparación (antes de la clase)
```powershell
# 1. Provisionar las 4 BDs de microservicios (una vez) en el servidor BBDD:
#    ejecutar microservicios_bds.sql (cierra la BD librospe_db con los datos)
#    y configurar en la app las variables:
#    MS_VENTAS_DB=librospe_ms_ventas
#    MS_INVENTARIO_DB=librospe_ms_inventario
#    MS_USUARIOS_DB=librospe_ms_usuarios
#    MS_CLIENTES_DB=librospe_ms_clientes

# 2. Correr la app local (debe quedar el servidor abierto)
run_local.bat

# 3. Probar la demo automatizada (local o producción)
# Local:
.\demo_microservicios.ps1 -Correo "admin@correo.com" -Clave "123456"
# Producción (alwaysdata):
.\demo_microservicios.ps1 -Produccion -Correo "admin@correo.com" -Clave "123456"
```
> Si no sabes el correo/admin, entra a `/login` en el navegador o consulta la tabla `usuarios_sistema` en la BD.

**Modo producción:** usa `-Produccion` para apuntar a `https://librospe.alwaysdata.net`.
También puedes usar `-BaseUrl "https://mi.dominio"` para cualquier otra URL.
El health check `/api/health` es público y se puede abrir directo en el navegador sin login:
```
https://librospe.alwaysdata.net/api/health
```

### Paso 1 — Arrancar la demo con el docente
```powershell
.\demo_microservicios.ps1 -Correo "admin@correo.com" -Clave "123456"
```
**Qué decir:** *"Voy a demostrar 5 microservicios —ventas, inventario, usuarios, clientes y monitor— y que cada uno vive en SU PROPIA base de datos."*

### Paso 2 — Monitor: prueba de las 4 BDs
El script muestra `GET /api/health`:
```json
{
  "status": "OK",
  "service": "LibrosPE microservicios",
  "version": "3.0",
  "bd_por_servicio": {
    "ventas": "librospe_ms_ventas",
    "inventario": "librospe_ms_inventario",
    "usuarios": "librospe_ms_usuarios",
    "clientes": "librospe_ms_clientes"
  },
  "services": { "ventas": "active", "inventario": "active", "usuarios": "active", "clientes": "active" },
  "timestamp": "..."
}
```
**Qué decir:** *"El monitor verifica en `information_schema` que cada servicio tiene su tabla representativa en su propia BD. Si no estuviera provisionada, aparecería 'not_configured'."*

### Paso 3 — Seguridad: sin sesión no se accede
El script llama a `/api/comercial/pedidos` **sin** cookie y muestra **HTTP 302 → /login**.
**Qué decir:** *"Cada microservicio hereda la autenticación del monolito mediante `login_required` inyectado. El único endpoint abierto es `/api/health` para monitoreo; los internos entre servicios usan `X-Service-Token`."*

### Paso 4 — Microservicio VENTAS
Muestra el total de pedidos/ventas y el detalle de un pedido (con sus líneas de detalle).
**Qué decir:** *"Estos datos salen de `comercial_pedidos` en `librospe_ms_ventas`. Al cambiar la BD de origen por un bind propio, el servicio sigue funcionando: ventas no toca tablas de inventario ni de clientes."*

### Paso 5 — Microservicio INVENTARIO
Muestra productos, los de stock bajo `< 10`, y la validación `verificar-stock`.
**Qué decir:** *"Inventario lee solo `inventario_productos` en `librospe_ms_inventario`. `/stock/bajo/10` implementa la alerta de stock. `verificar-stock` es lo que el POS usa antes de confirmar una venta."*

### Paso 6 — Microservicio USUARIOS
Muestra usuarios del sistema y roles (BD `librospe_ms_usuarios`).
**Qué decir:** *"La seguridad de la app es otro microservicio: sus datos de usuario/rol viven en su propia BD y se exponen por su propia API."*

### Paso 7 — Microservicio CLIENTES
Muestra clientes registrados y el resumen por ubicación (BD `librospe_ms_clientes`).
**Qué decir:** *"El catálogo de clientes es también un microservicio independiente."*

### Paso 8 — INTEGRACIÓN: ventas consulta a inventario por HTTP
`GET /api/comercial/validar-stock/<id>/<cant>` → ventas **llama por HTTP** al endpoint interno `_verificar-stock` de inventario con `X-Service-Token`.
**Qué decir:** *"Aquí está la clave: ventas NECESITA saber el stock, pero NO puede leer la BD de inventario. Por eso inventario publicó un endpoint interno protegido por token y ventas lo consulta por HTTP. Es la comunicación real entre microservicios."*

> **Nota (producción):** cuando la app corre en un solo proceso uWSGI
> (`processes = 1`, como en alwaysdata), una llamada HTTP a la propia URL se
> autobloquea hasta el timeout → 503. Por eso
> `microservicios.es_llamada_a_si_mismo()` detecta ese caso y ventas resuelve el
> stock **en proceso** (misma lógica de inventario), manteniendo HTTP + token
> cuando los servicios son procesos separados (demo local en 8001-8004). En ese
> caso la respuesta indica `"consulto_a": "inventario (en proceso ...)"`.

### Paso 9 — (Opcional) Escritura solo admin
```powershell
.\demo_microservicios.ps1 -Correo "admin@correo.com" -Clave "123456" -EjecutarEscritura
```
Prueba los `PUT` de cambio de estado (ventas) y de stock (inventario) **sobre las BDs propias**. Con un vendedor devuelve **403**.
**Qué decir:** *"Las operaciones que modifican datos validan además el rol de administrador: otra capa de seguridad por microservicio."*

### Paso 10 — Cierre visual (admin)
Abrir en el navegador: `http://localhost:8000/microservicios/dashboard`
(o `https://librospe.alwaysdata.net/microservicios/dashboard` en producción).
Muestra KPIs: pedidos totales/pendientes/confirmados y productos totales/bajo stock/agotados, contados desde la BD propia de cada servicio.

---

## 3. Posibles preguntas del docente (y respuestas)

**¿Son microservicios reales o solo carpetas?**
Cada microservicio es un blueprint Flask con `url_prefix` propio, **su propia base de datos MySQL** (bind de SQLAlchemy configurado en `app.py`) y su API. Se comunican por HTTP (`/api/comercial/validar-stock` → inventario). Es una arquitectura *modular-monolith* lista para extraerse a procesos/servidores independientes: cada servicio solo depende de `db` y `login_required`, que se inyectan.

**¿Por qué antes compartían base?**
Por rapidez de despliegue. Ahora cada servicio tiene su BD (`librospe_ms_ventas`, `librospe_ms_inventario`, `librospe_ms_usuarios`, `librospe_ms_clientes`) y las tablas espejo viven en esos schemas. La app usa variables `MS_*_DB` con fallback a la BD principal si no se provisionan (para no romper el sistema).

**¿Cómo evitar imports circulares?**
Las dependencias se pasan por inyección en `register_microservicios(app, db, login_required)` (www/microservicios/__init__.py:59). El paquete no importa `app.py`; `app.py` lo registra al final.

**¿Y los datos de una BD a otra?**
Los datos se replican con `microservicios_bds.sql` (carga inicial). La sincronización programada sigue en `sincronizar*.sh`.

**¿Cómo se prueba que cada microservicio está activo?**
Con `/api/health`, que verifica en `information_schema` la existencia de la tabla representativa de cada servicio en SU BD (www/microservicios/routes_monitor.py).

**¿Y si un servicio no está provisionado?**
El health reporta `not_configured`, y la app cae al fallback (BD principal) para que el sistema siga funcionando.

---

## 4. Ficha técnica (para el informe)

- **Ubicación:** `www/microservicios/__init__.py`, `routes_comercial.py`, `routes_inventario.py`, `routes_usuarios.py`, `routes_clientes.py`, `routes_monitor.py`
- **Configuración de BDs:** `www/app.py` → `SQLALCHEMY_BINDS` con variables `MS_VENTAS_DB`, `MS_INVENTARIO_DB`, `MS_USUARIOS_DB`, `MS_CLIENTES_DB`, `SERVICE_TOKEN` y `MS_INVENTARIO_URL`
- **Provisionamiento de BDs:** `microservicios_bds.sql` (raíz del repo)
- **Registro:** `www/app.py` → `register_microservicios(app, db, login_required)`
- **Integración HTTP:** `routes_comercial.py` `_consultar_inventario()` + `_verificar-stock` en `routes_inventario.py` con `servicio_requerido` (token interno)
- **Dashboard:** `GET /microservicios/dashboard` (solo admin) → `templates/microservicios_dashboard.html`
- **Demo automatizada:** `demo_microservicios.ps1` (raíz del repo)