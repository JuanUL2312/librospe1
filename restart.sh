#!/bin/bash
# Reinicia LibrosPE (local o alwaysdata).
# Resuelve las rutas desde la ubicacion de este script, no desde rutas fijas.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/www"

echo "================"
echo "Reiniciando LibrosPE..."
echo "App: $APP_DIR"
echo "================"

# Crear directorio tmp si no existe
mkdir -p "$APP_DIR/tmp"

# Tocar archivo de reinicio (Passenger)
touch "$APP_DIR/tmp/restart.txt"

# Tocar wsgi.py y passenger_wsgi.py para forzar recarga
touch "$APP_DIR/passenger_wsgi.py"
touch "$APP_DIR/wsgi.py"

echo "Aplicacion reiniciada correctamente"
echo "Espera 5-10 segundos para que Passenger recargue"