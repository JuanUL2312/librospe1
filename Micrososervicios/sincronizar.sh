#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"

if [[ ! -r "$ENV_FILE" ]]; then
  echo "No se encontró el archivo de configuración: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a
: "${DB_USER:?Falta DB_USER}" "${DB_PASSWORD:?Falta DB_PASSWORD}" "${DB_HOST:?Falta DB_HOST}" "${DB_NAME:?Falta DB_NAME}"

MYSQL_PWD="$DB_PASSWORD" mysql --host="$DB_HOST" --user="$DB_USER" "$DB_NAME" < "$SCRIPT_DIR/sincronizar.sql"
