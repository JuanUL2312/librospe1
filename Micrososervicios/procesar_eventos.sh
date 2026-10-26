#!/usr/bin/env bash
# =============================================================================
# AGENTE DE MENSAJES - reintento de los eventos pendientes (outbox)
# -----------------------------------------------------------------------------
# Cuando el broker RabbitMQ no esta disponible, el gateway guarda los eventos
# en la tabla `eventos_pendientes`. Este script (cron) reintenta publicarlos.
# Si no hay broker configurado, no hace nada (los eventos se acumulan).
# =============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME="${HOME:-/home/librospe}"

if [[ -r "${HOME}/.env" ]]; then
  ENV_FILE="${ENV_FILE:-$HOME/.env}"
elif [[ -r "$SCRIPT_DIR/.env" ]]; then
  ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"
else
  ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"
fi
LOG_FILE="${EVENTOS_LOG_FILE:-$HOME/eventos.log}"
if [[ ! -w "$(dirname "$LOG_FILE")" ]]; then
  LOG_FILE="${EVENTOS_LOG_FILE:-$SCRIPT_DIR/eventos.log}"
fi

if [[ ! -r "$ENV_FILE" ]]; then
  echo "No se encontró el archivo de configuración: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${AMQP_URL:-}" ]]; then
  echo "ℹ️  AMQP_URL no configurado: no hay broker de mensajes activo." | tee -a "$LOG_FILE"
  exit 0
fi

echo "=========================================" | tee -a "$LOG_FILE"
echo "📨 REINTENTO DE EVENTOS (agente de mensajes)" | tee -a "$LOG_FILE"
echo "📅 $(date)" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"

if [[ -d "$HOME/www" ]]; then
  WWW="$HOME/www"
else
  WWW="$SCRIPT_DIR/www"
fi
cd "$WWW"

if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi
PYTHON="${PY:-python3}"
if [[ -x "$HOME/www/venv/bin/python" ]]; then
  PYTHON="$HOME/www/venv/bin/python"
fi
# Este cron publica outbox y reconcilia sagas pendientes. Evita arrancar
# consumidores en segundo plano durante una tarea programada.
export OUTBOX_WORKER=1
"$PYTHON" - <<'PY' 2>&1 | tee -a "$LOG_FILE"
try:
    from mensajeria import procesar_outbox, estado
    from app import reconciliar_reservas_stock
    enviados, fallidos = procesar_outbox(500)
    confirmadas, canceladas, pendientes = reconciliar_reservas_stock(200)
    print(f"Eventos publicados: {enviados} | pendientes: {fallidos}")
    print(f"Reservas confirmadas: {confirmadas} | pedidos cancelados: {canceladas} "
          f"| stock pendiente: {pendientes}")
    info = estado()
    print(f"Broker: {'conectado' if info.get('broker') else 'no disponible'}")
except Exception as e:
    print(f"Error procesando eventos o conciliando reservas: {e}")
PY

echo "=========================================" | tee -a "$LOG_FILE"
echo "" >> "$LOG_FILE"
