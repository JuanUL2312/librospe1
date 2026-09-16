# Guía de demostración: Microservicios de LibrosPE

Presentación ante docente. Objetivo: mostrar que la aplicación se divide en **dominios de negocio independientes** (microservicios) aunque comparten la misma base de datos.

---

## 1. Resumen para presentar (2 min)

| Microservicio | Prefijo | Responsabilidad | Tablas espejo (dominio propio) |
|---|---|---|---|
| **comercial** | `/api/comercial` | Pedidos y ventas | `comercial_pedidos`, `comercial_detalle_pedido`, `comercial_ventas` |
| **inventario** | `/api/inventario` | Productos y stock | `inventario_productos`, `inventario_categorias` |
| **monitor** | `/api` | Health check | `information_schema` (verifica las tablas espejo) |

**Idea clave:** cada microservicio es un *blueprint Flask* independiente en el paquete `www/microservicios/`, con su propio `url_prefix` y leyendo **solo** sus tablas espejo. No hay imports circulares: las dependencias compartidas (`db` y `login_required`) se inyectan en `register_microservicios()` (www/microservicios/__init__.py:23).

**Endpoints:**
- `GET  /api/health` → estado de los servicios (público)
- `GET  /api/comercial/pedidos` → pedidos
- `GET  /api/comercial/pedidos/<id>` → pedido + detalles
- `PUT  /api/comercial/pedidos/<id>/estado` → cambiar estado (solo admin)
- `GET  /api/comercial/ventas` → ventas
- `GET  /api/inventario/productos` → productos
- `GET  /api/inventario/productos/<id>` → producto
- `PUT  /api/inventario/stock/<id>` → actualizar stock (solo admin)
- `GET  /api/inventario/stock/bajo/<min>` → stock bajo
- `GET  /api/inventario/verificar-stock/<id>/<cant>` → validación de stock

---

## 2. Guion de demostración (10-15 min)

### Paso 0 — Preparación (antes de la clase)
```powershell
# 1. Correr la app local (debe quedar el servidor abierto)
run_local.bat

# 2. Probar la demo automatizada
.\demo_microservicios.ps1 -Correo "admin@correo.com" -Clave "123456"
```
> Si no sabes el correo/admin, entra a `/login` en el navegador o consulta la tabla `usuarios_sistema` en la BD.

### Paso 1 — Arrancar la demo con el docente
```powershell
.\demo_microservicios.ps1 -Correo "admin@correo.com" -Clave "123456"
```
**Qué decir:** *"Voy a demostrar que el sistema está separado en 3 microservicios: comercial, inventario y monitor. Primero veremos el health check que los monitorea."*

### Paso 2 — Monitor: prueba que los servicios están "activos"
El script muestra `GET /api/health`:
```json
{
  "status": "OK",
  "service": "LibrosPE microservicios",
  "version": "2.0",
  "services": { "comercial": "active", "inventario": "active" },
  "timestamp": "..."
}
```
**Qué decir:** *"El microservicio monitor consulta la base de datos y verifica que existen las tablas espejo de comercial e inventario. Si faltaran, aparecería 'not_configured'."*

### Paso 3 — Seguridad: sin sesión no se accede
El script llama a `/api/comercial/pedidos` **sin** cookie y muestra **HTTP 302 → /login**.
**Qué decir:** *"Cada microservicio hereda la autenticación del monolito mediante `login_required` inyectado. No hay endpoints abiertos, salvo el health check para monitoreo."*

### Paso 4 — Microservicio COMERCIAL
Muestra el total de pedidos/ventas y el detalle de un pedido (con sus líneas de detalle).
**Qué decir:** *"Estos datos salen de la tabla `comercial_pedidos`, dominio exclusivo de comercial. El microservicio no toca tablas de inventario."*

### Paso 5 — Microservicio INVENTARIO
Muestra productos, los de stock bajo `< 10`, y la validación `verificar-stock`.
**Qué decir:** *"Inventario lee solo `inventario_productos`. La ruta `/stock/bajo/10` implementa la alerta de stock, y `verificar-stock` es el endpoint que el POS podría usar antes de confirmar una venta."*

### Paso 6 — (Opcional) Escritura solo admin
```powershell
.\demo_microservicios.ps1 -Correo "admin@correo.com" -Clave "123456" -EjecutarEscritura
```
Prueba los `PUT` de cambio de estado (`comercial`) y de stock (`inventario`). Con un vendedor devuelve **403**.
**Qué decir:** *"Las operaciones que modifican datos validan además el rol de administrador. Es otra capa de seguridad por microservicio."*

### Paso 7 — Cierre visual (admin)
Abrir en el navegador: `http://localhost:8000/microservicios/dashboard`
Muestra KPIs: pedidos totales/pendientes/confirmados y productos totales/bajo stock/agotados, contados desde las tablas espejo.

---

## 3. Posibles preguntas del docente (y respuestas)

**¿Son microservicios reales o solo carpetas?**
Son blueprints Flask independientes con `url_prefix` propio y dominio de datos separado (tablas espejo diseñadas en `migracion_nuevas_tablas.sql`). Es una arquitectura *modular-monolith*: cada servicio se puede extraer a un proceso/servidor propio sin cambiar su código interno, porque no depende de nada del monolito salvo `db` y `login_required`, que se inyectan.

**¿Por qué comparten base de datos?**
Para el alcance del proyecto, usar una BD compartida simplifica despliegue en alwaysdata. El aislamiento se garantiza con **tablas espejo** (`comercial_*`, `inventario_*`): ningún servicio lee tablas de otro dominio.

**¿Cómo evitas imports circulares?**
Las dependencias se pasan por inyección en `register_microservicios(app, db, login_required)` (www/microservicios/__init__.py:23). El paquete no importa `app.py`; `app.py` lo registra al final (www/app.py:5310).

**¿Dónde está la sincronización?**
Los scripts `sincronizar*.sh` sincronizan las tablas espejo desde las tablas principales (`sincronizar.sql`), programado por cron cada hora.

**¿Cómo se prueba que un microservicio está activo?**
Con `/api/health`, que verifica en `information_schema` la existencia de las tablas espejo de cada servicio (www/microservicios/routes_monitor.py:16).

---
## 4. Ficha técnica (para el informe)

- **Ubicación:** `www/microservicios/__init__.py`, `routes_comercial.py`, `routes_inventario.py`, `routes_monitor.py`
- **Registro:** `www/app.py:5310` → `register_microservicios(app, db, login_required)`
- **Migración de tablas espejo:** `migracion_nuevas_tablas.sql`
- **Dashboard:** `GET /microservicios/dashboard` (solo admin) → `templates/microservicios_dashboard.html`
- **Demo automatizada:** `demo_microservicios.ps1` (raíz del repo)