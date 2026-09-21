#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"
LOG_FILE="${SYNC_LOG_FILE:-$SCRIPT_DIR/sincronizacion.log}"

if [[ ! -r "$ENV_FILE" ]]; then
  echo "No se encontró el archivo de configuración: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a
: "${DB_USER:?Falta DB_USER}" "${DB_PASSWORD:?Falta DB_PASSWORD}" "${DB_HOST:?Falta DB_HOST}" "${DB_NAME:?Falta DB_NAME}"

echo "=========================================" | tee -a $LOG_FILE
echo "🔄 SINCRONIZACIÓN MICROSERVICIOS" | tee -a $LOG_FILE
echo "📅 $(date)" | tee -a $LOG_FILE
echo "=========================================" | tee -a $LOG_FILE

MYSQL_PWD="$DB_PASSWORD" mysql --host="$DB_HOST" --user="$DB_USER" "$DB_NAME" < "$SCRIPT_DIR/sincronizar.sql" 2>&1 | tee -a "$LOG_FILE"

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "✅ SINCRONIZACIÓN COMPLETADA EXITOSAMENTE" | tee -a $LOG_FILE
else
    echo "❌ ERROR EN LA SINCRONIZACIÓN" | tee -a $LOG_FILE
fi

echo "=========================================" | tee -a $LOG_FILE
echo "" >> $LOG_FILE
