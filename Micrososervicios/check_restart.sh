#!/bin/bash
# Verifica el reinicio de LibrosPE (local o alwaysdata).
# Resuelve las rutas desde la ubicacion de este script.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/www"

echo "================"
echo "Estado de reinicio de LibrosPE ($APP_DIR)"
echo "================"

if [ -f "$APP_DIR/tmp/restart.txt" ]; then
    LAST_RESTART=$(stat -c %y "$APP_DIR/tmp/restart.txt")
    echo "Ultimo reinicio: $LAST_RESTART"
else
    echo "Archivo restart.txt no existe"
fi

echo "Estado de Passenger:"
passenger-status 2>/dev/null || echo "No se puede obtener status"