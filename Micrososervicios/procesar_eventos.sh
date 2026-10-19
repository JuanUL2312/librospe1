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
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"
LOG_FILE="${EVENTOS_LOG_FILE:-$SCRIPT_DIR/eventos.log}"

if [[ ! -r "$ENV_FILE" ]]; then
  echo "No se encontró el archivo de configuración: $ENV_FILE" >&2
  exit 1
fi

set -a
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

cd "$SCRIPT_DIR/www"
if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi
python3 - <<'PY' 2>&1 | tee -a "$LOG_FILE"
try:
    from mensajeria import procesar_outbox, estado
    enviados, fallidos = procesar_outbox(500)
    print(f"📤 Eventos publicados: {enviados} | pendientes: {fallidos}")
    info = estado()
    print(f"🔌 Broker: {'conectado' if info.get('broker') else 'no disponible'}")
except Exception as e:
    print(f"❌ Error procesando los eventos: {e}")
PY

echo "=========================================" | tee -a "$LOG_FILE"
echo "" >> "$LOG_FILE"
