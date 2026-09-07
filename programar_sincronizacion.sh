#!/bin/bash

echo "========================================="
echo "📅 PROGRAMAR SINCRONIZACIÓN AUTOMÁTICA"
echo "========================================="

# Eliminar tarea anterior si existe
(crontab -l 2>/dev/null | grep -v "sincronizar_completo.sh") | crontab -

# Agregar nueva tarea (cada hora)
(crontab -l 2>/dev/null; echo "0 * * * * ~/sincronizar_completo.sh >> ~/sincronizacion.log 2>&1") | crontab -

echo "✅ Sincronización programada para ejecutarse cada hora"
echo ""
echo "📋 Configuración actual de cron:"
crontab -l
