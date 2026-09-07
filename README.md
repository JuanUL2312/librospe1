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

## ⚙️ Configuración

Copia `.env.example` a `.env` y configura tus credenciales (BD, email, `SECRET_KEY`).
