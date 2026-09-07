#!/bin/bash
echo "🔄 Reiniciando LibrosPE..."

# Crear directorio tmp si no existe
mkdir -p /home/librospe/www/tmp

# Tocar archivo de reinicio
touch /home/librospe/www/tmp/restart.txt

# También tocar passenger_wsgi.py para forzar recarga
touch /home/librospe/www/passenger_wsgi.py

echo "✅ Aplicación reiniciada correctamente"
echo "📝 Espera 5-10 segundos para que Passenger recargue"
