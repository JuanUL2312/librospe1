#!/bin/bash
if [ -f /home/librospe/www/tmp/restart.txt ]; then
    LAST_RESTART=$(stat -c %y /home/librospe/www/tmp/restart.txt)
    echo "🕐 Último reinicio: $LAST_RESTART"
else
    echo "❌ Archivo restart.txt no existe"
fi

# Ver uptime de Passenger
echo "📊 Estado de Passenger:"
passenger-status 2>/dev/null || echo "No se puede obtener status"
