#!/usr/bin/env bash
# Cron recomendado (panel Alwaysdata, cada 5 min):
#   bash /home/librospe/mantener_produccion.sh
# 1) microservicios HTTP  2) outbox RabbitMQ  3) keep-alive del worker uWSGI
set -Eeuo pipefail

HOME="${HOME:-/home/librospe}"
LOGDIR="${LOGDIR:-$HOME/logs}"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/mantener_produccion.log"
{
  echo "===== $(date -Is) ====="
  if [[ -x "$HOME/iniciar_servicios_api.sh" ]]; then
    bash "$HOME/iniciar_servicios_api.sh" || true
  elif [[ -x "$HOME/Micrososervicios/iniciar_servicios_api.sh" ]]; then
    bash "$HOME/Micrososervicios/iniciar_servicios_api.sh" || true
  fi
  if [[ -x "$HOME/procesar_eventos.sh" ]]; then
    bash "$HOME/procesar_eventos.sh" || true
  fi
  curl -fsS -m 20 "https://librospe.alwaysdata.net/api/health" >/dev/null || true
} >> "$LOG" 2>&1
