# LibrosPE

Aplicación web de librería/tienda online construida con **Flask** + **MySQL**.

## 🖥️ Entornos de ejecución

El proyecto puede correr en **dos entornos**:

### 1. Producción (nube) — alwaysdata

La app se despliega en alwaysdata usando **Passenger/uWSGI**.
Los archivos de configuración del servidor son:

- `www/wsgi.py` y `www/passenger_wsgi.py` → punto de entrada WSGI
- `www/.htaccess` → configuración de Passenger
- `www/venv/` → entorno virtual **Linux** del servidor
- `restart.sh` → reinicia la app (toca `www/tmp/restart.txt`)

La base de datos y el email se configuran en `.env` (no se sube a Git).

### 2. Local (desarrollo) — Live Server

Para correr en tu máquina (Windows) usa el entorno virtual local **`.venv-live`**.

**Arranque rápido:**
```bash
# Doble clic o desde la terminal:
run_local.bat
```

Luego abre en el navegador: **http://localhost:8000**

El entorno local se conecta a la misma base de datos de la nube (según `.env`),
así que verás los mismos datos en local y en producción.

**Si falta el entorno virtual local:**
```bash
python -m venv .venv-live
.venv-live\Scripts\pip install -r requirements.txt
```

## 🔄 Sincronización de microservicios

- `sincronizar.sh` → ejecuta `sincronizar.sql` (sincroniza pedidos, productos y proveedores)
- `verificar_sincronizacion.sh` → muestra el estado de sincronización
- `programar_sincronizacion.sh` → agenda el job cada hora vía cron
- `sincronizar_completo.sh` → versión con log

## 🗺️ Ubigeo (departamento, provincia y distrito)

Al registrar un cliente se solicitan **departamento, provincia y distrito** (selects en cascada).
Estos valores se guardan en el cliente y se alimentan de las tablas `departamentos`, `provincias` y `distritos`
(ubigeo del Perú, fuente INEI).

Para poblar esas tablas la primera vez, ejecuta:

```bash
cd www
python seed_ubigeo.py
```

El script es idempotente (no duplica datos si ya existen).

Los **usuarios del sistema** (vendedores/administradores) pueden registrar su **DNI o Carnet de Extranjería**
(campo `documento` en la tabla `usuarios_sistema`) al crear un nuevo usuario.

## 💵 Caja y vuelto (tienda presencial)

- **Apertura y cierre de caja** (`/caja`): se abre la caja con un monto inicial, se registran las ventas
del turno (resumen por método de pago) y al cerrar se compara el **monto esperado** vs. el **monto real**
contado, calculando la **diferencia**.
- **Método de pago y vuelto**: en el formulario de nueva venta (`/ventas/nueva`) se elige el método de pago
(efectivo, tarjeta, Yape o Plin). Si pagas en **efectivo**, se ingresa el monto recibido y el sistema calcula
automáticamente el **vuelto** (o el faltante).

## ⚠️ Alertas de stock configurables

Cada producto tiene **stock mínimo** y **stock máximo** configurables (en el formulario de producto).
El sistema alerta automáticamente:
- **Stock bajo** cuando la cantidad cae por debajo del mínimo.
- **Agotado** cuando llega a 0.
- **Exceso de stock** cuando supera el máximo.

Las alertas se muestran en el **listado de productos** (badges) y en el **dashboard**.

## 📄 Exportar reportes a PDF

- **Reporte de ventas** (`/reportes/ventas/pdf`): exporta las ventas a PDF (el vendedor ve solo las suyas).
  Botón **"Exportar PDF"** en la página de ventas.
- **Cierre de caja** (`/caja/cierre/pdf`): exporta el cierre de caja a PDF con el resumen por método de pago,
  montos esperado/real y diferencia. Botón de PDF en el historial de caja.

Requiere las librerías `reportlab` y `openpyxl` (incluidas en `requirements.txt`).

## 🔐 Seguridad y auditoría

- **Cambio de contraseña obligatorio**: los usuarios nuevos (vendedores) se crean con clave `123456` y
  deben cambiarla al primer ingreso (campo `debe_cambiar_clave`).
- **Auditoría** (`/auditoria`): registra quién creó/modificó/eliminó productos, proveedores, ventas y usuarios.
  Solo visible para administradores.

## 🧾 Comprobante PDF con autorización SUNAT simulada

En la vista del comprobante hay un botón **"Descargar PDF"** que genera el PDF de la boleta/factura con una
**autorización SUNAT simulada** (serie-número + hash), ideal para la demostración del proyecto sin pagar
un proveedor SUNAT real.

## 🔑 Permisos por rol configurables

- Tablas `permisos` y `rol_permisos` (el rol **administrador** tiene todos los permisos).
- Decorador `@permiso_requerido(...)` aplicado a dashboard, caja, auditoría, gestión de productos/proveedores,
  usuarios y reportes. Se puede asignar permisos a otros roles desde la BD.

## 🛡️ Otras mejoras de seguridad

- **Límite de intentos en el POS**: control anti-doble clic para evitar ventas duplicadas.
- **Costo oculto al vendedor**: campo `costo` en productos (precio de compra) que solo ve/edita el admin.
- **Notificación de stock bajo**: se envía un correo automático al administrador cuando un producto cae
  por debajo de su stock mínimo.

## ⚙️ Configuración

Copia `.env.example` a `.env` y configura tus credenciales (BD, email, `SECRET_KEY`).
