# LibrosPE

AplicaciÃ³n web de librerÃ­a/tienda online construida con **Flask** + **MySQL**.

## ðŸ–¥ï¸ Entornos de ejecuciÃ³n

El proyecto puede correr en **dos entornos**:

### 1. ProducciÃ³n (nube) â€” alwaysdata

La app se despliega en alwaysdata usando **Passenger/uWSGI**.
Los archivos de configuraciÃ³n del servidor son:

- `www/wsgi.py` y `www/passenger_wsgi.py` â†’ punto de entrada WSGI
- `www/.htaccess` â†’ configuraciÃ³n de Passenger
- `www/venv/` â†’ entorno virtual **Linux** del servidor
- `local/admin/restart.sh` es una utilidad para Passenger local; con uWSGI en Alwaysdata, reinicia desde el panel.

La base de datos y el email se configuran en `.env` (no se sube a Git).

**Despliegue de cambios (vÃ­a SSH):**

```bash
# 1) Descargar el cÃ³digo actualizado a una carpeta temporal
cd ~
git clone https://github.com/JuanUL2312/librospe1.git librospe1

# 2) Sincronizar SOLO los archivos de la web a la raÃ­z del sitio
#    (conserva venv/ y .env del servidor)
rsync -a --exclude 'venv' --exclude '.env' librospe1/www/ ~/www/

# 3) Reiniciar la app: con uWSGI el reinicio es desde el panel de
#    alwaysdata (Web > Sites > tu sitio > Restart). touch restart.txt
#    solo funciona en sitios Passenger.
```

> NO usar `rsync --delete`: borrarÃ­a `~/www/venv/`. Tampoco sobrescribir `~/www/.env`
> (mantiene la SECRET_KEY, BD y correo del servidor). Los `static/css` y `static/js`
> nuevos se incluyen en el rsync.

**VerificaciÃ³n tras el despliegue:**

```bash
curl -s https://librospe.alwaysdata.net/api/health
# {"status":"OK","services":{"comercial":"active","inventario":"active"}, "version":"2.0"}
```

Alternativa desde el panel: activar la integraciÃ³n **Git** del sitio en alwaysdata
apuntando a este repositorio y reiniciar la app desde el panel.

### 2. Local (desarrollo) â€” Live Server

Para correr en tu mÃ¡quina (Windows) usa el entorno virtual local **`.venv-live`**.

**Arranque rÃ¡pido:**
```bash
# Doble clic o desde la terminal:
local\windows\run_local.bat
```

Luego abre en el navegador: **http://localhost:8000**

El entorno local se conecta a la misma base de datos de la nube (segÃºn `.env`),
asÃ­ que verÃ¡s los mismos datos en local y en producciÃ³n.

**Si falta el entorno virtual local:**
```bash
python -m venv .venv-live
.venv-live\Scripts\pip install -r requirements.txt
```

## ðŸ§ª Pruebas (pytest)

La suite estÃ¡ en `tests/` y cubre las 6 categorÃ­as:

```bash
.venv-live\Scripts\python -m pytest -c local/dev/pytest.ini tests  # toda la suite
.venv-live\Scripts\python -m pytest -c local/dev/pytest.ini tests -m unitarias    # sin red ni BD
.venv-live\Scripts\python -m pytest -c local/dev/pytest.ini tests -m resiliencia  # caÃ­da de servicios -> 503
```

Los fixtures levantan solos los microservicios (8001-8004) y el gateway
(8000) si no estÃ¡n corriendo, y solo detienen los procesos que ellos
arrancaron. Las categorÃ­as que escriben en la BD usan filas de prueba que
se eliminan al final.

## ðŸ”„ SincronizaciÃ³n de microservicios

- `sincronizar_completo.sh` â†’ ejecuta `sincronizar.sql` y registra todo en `sincronizacion.log`
- `local/admin/verificar_sincronizacion.sh` muestra el estado de sincronizaci?n desde un equipo con acceso MySQL.
- `programar_sincronizacion.sh` â†’ agenda el job cada hora vÃ­a cron (en alwaysdata se usa el cron del panel)

## ðŸ—ºï¸ Ubigeo (departamento, provincia y distrito)

Al registrar un cliente se solicitan **departamento, provincia y distrito** (selects en cascada).
Estos valores se guardan en el cliente y se alimentan de las tablas `departamentos`, `provincias` y `distritos`
(ubigeo del PerÃº, fuente INEI).

Para poblar esas tablas la primera vez, ejecuta:

```bash
cd www
python seed_ubigeo.py
```

El script es idempotente (no duplica datos si ya existen).

Los **usuarios del sistema** (vendedores/administradores) pueden registrar su **DNI o Carnet de ExtranjerÃ­a**
(campo `documento` en la tabla `usuarios_sistema`) al crear un nuevo usuario.

## ðŸ’µ Caja y vuelto (tienda presencial)

- **Apertura y cierre de caja** (`/caja`): se abre la caja con un monto inicial, se registran las ventas
del turno (resumen por mÃ©todo de pago) y al cerrar se compara el **monto esperado** vs. el **monto real**
contado, calculando la **diferencia**.
- **MÃ©todo de pago y vuelto**: en el formulario de nueva venta (`/ventas/nueva`) se elige el mÃ©todo de pago
(efectivo, tarjeta, Yape o Plin). Si pagas en **efectivo**, se ingresa el monto recibido y el sistema calcula
automÃ¡ticamente el **vuelto** (o el faltante).

## âš ï¸ Alertas de stock configurables

Cada producto tiene **stock mÃ­nimo** y **stock mÃ¡ximo** configurables (en el formulario de producto).
El sistema alerta automÃ¡ticamente:
- **Stock bajo** cuando la cantidad cae por debajo del mÃ­nimo.
- **Agotado** cuando llega a 0.
- **Exceso de stock** cuando supera el mÃ¡ximo.

Las alertas se muestran en el **listado de productos** (badges) y en el **dashboard**.

## ðŸ“„ Exportar reportes a PDF

- **Reporte de ventas** (`/reportes/ventas/pdf`): exporta las ventas a PDF (el vendedor ve solo las suyas).
  BotÃ³n **"Exportar PDF"** en la pÃ¡gina de ventas.
- **Cierre de caja** (`/caja/cierre/pdf`): exporta el cierre de caja a PDF con el resumen por mÃ©todo de pago,
  montos esperado/real y diferencia. BotÃ³n de PDF en el historial de caja.
- **Reporte de ventas por ubicaciÃ³n** (`/reportes/ventas_por_ubicacion`): reporte de ventas por cliente agrupado
  en la jerarquÃ­a **departamento â†’ provincia â†’ distrito â†’ cliente**, con filtros por perÃ­odo y departamento,
  exportable a PDF y Excel (botones en la pÃ¡gina).

Requiere las librerÃ­as `reportlab` y `openpyxl` (incluidas en `requirements.txt`).

## ðŸ” Seguridad y auditorÃ­a

- **Cambio de contraseÃ±a obligatorio**: los usuarios nuevos (vendedores) se crean con clave `123456` y
  deben cambiarla al primer ingreso (campo `debe_cambiar_clave`).
- **AuditorÃ­a** (`/auditoria`): registra quiÃ©n creÃ³/modificÃ³/eliminÃ³ productos, proveedores, ventas y usuarios.
  Solo visible para administradores.

## ðŸ§¾ Comprobante PDF con autorizaciÃ³n SUNAT simulada

En la vista del comprobante hay un botÃ³n **"Descargar PDF"** que genera el PDF de la boleta/factura con una
**autorizaciÃ³n SUNAT simulada** (serie-nÃºmero + hash), ideal para la demostraciÃ³n del proyecto sin pagar
un proveedor SUNAT real.

## ðŸ”‘ Permisos por rol configurables

- Tablas `permisos` y `rol_permisos` (el rol **administrador** tiene todos los permisos).
- Decorador `@permiso_requerido(...)` aplicado a dashboard, caja, auditorÃ­a, gestiÃ³n de productos/proveedores,
  usuarios y reportes. Se puede asignar permisos a otros roles desde la BD.

## ðŸ›¡ï¸ Otras mejoras de seguridad

- **LÃ­mite de intentos en el POS**: control anti-doble clic para evitar ventas duplicadas.
- **Costo oculto al vendedor**: campo `costo` en productos (precio de compra) que solo ve/edita el admin.
- **NotificaciÃ³n de stock bajo**: se envÃ­a un correo automÃ¡tico al administrador cuando un producto cae
  por debajo de su stock mÃ­nimo.

## âš™ï¸ ConfiguraciÃ³n

Copia `.env.example` a `.env` y configura tus credenciales (BD, email, `SECRET_KEY`).

