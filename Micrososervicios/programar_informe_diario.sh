#!/bin/bash

echo "========================================="
echo "? PROGRAMAR INFORME DIARIO POR CORREO"
echo "========================================="
echo "El informe resume ventas de las ultimas 24 h, caja, stock bajo"
echo "y pedidos nuevos, y se envia a los administradores."
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFORME="$SCRIPT_DIR/www/informe_diario.py"

# Eliminar tarea anterior si existe
(crontab -l 2>/dev/null | grep -v "informe_diario.py") | crontab -

# Agregar nueva tarea (todos los dias a las 22:30)
(crontab -l 2>/dev/null; echo "30 22 * * * cd $SCRIPT_DIR/www && /usr/bin/python3 $INFORME >> $SCRIPT_DIR/informe_diario.log 2>&1") | crontab -

echo "?. Informe diario programado para las 22:30"
echo ""
echo "?< Configuracion actual de cron:"
crontab -l
