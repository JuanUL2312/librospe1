#!/usr/bin/env bash
# Idempotente: levanta inventario/ventas/usuarios/clientes en 127.0.0.1:8001-8004
# si /health no responde. Prefiere gunicorn; si no está, Flask threaded.
set -Eeuo pipefail

HOME="${HOME:-/home/librospe}"
PY="${PY:-$HOME/www/venv/bin/python}"
LOGDIR="${LOGDIR:-$HOME/logs}"
mkdir -p "$LOGDIR"

if [[ -r "$HOME/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$HOME/.env"
  set +a
fi

hay_gunicorn=0
if "$PY" -c "import gunicorn" >/dev/null 2>&1; then
  hay_gunicorn=1
fi

arrancar() {
  local nombre="$1"
  local puerto="$2"
  local dir="$HOME/$nombre"
  if "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${puerto}/health', timeout=2)" >/dev/null 2>&1; then
    echo "ya arriba $nombre (:$puerto)"
    return 0
  fi
  if [[ ! -d "$dir" ]]; then
    echo "FALTA_DIR $dir"
    return 1
  fi
  (
    cd "$dir" || exit 1
    if [[ "$hay_gunicorn" -eq 1 ]]; then
      nohup "$PY" -m gunicorn \
        --bind "127.0.0.1:${puerto}" \
        --workers 1 --threads 4 --timeout 45 \
        --pid "$LOGDIR/${nombre}.pid" \
        --error-logfile "$LOGDIR/${nombre}.err.log" \
        --access-logfile "$LOGDIR/${nombre}.access.log" \
        app:app </dev/null >> "$LOGDIR/${nombre}.out" 2>&1 &
    else
      nohup "$PY" app.py </dev/null >> "$LOGDIR/${nombre}.out" 2>&1 &
    fi
    echo "$(date -Is) iniciado $nombre (:$puerto) pid $!"
  ) >> "$LOGDIR/api_servicios.log"
}

arrancar servicio-inventario 8001
arrancar servicio-ventas 8002
arrancar servicio-usuarios 8003
arrancar servicio-clientes 8004
sleep 3

fallos=0
for s in servicio-inventario:8001 servicio-ventas:8002 servicio-usuarios:8003 servicio-clientes:8004; do
  puerto="${s##*:}"
  if "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${puerto}/health', timeout=6)" >/dev/null 2>&1; then
    echo "HEALTH_OK $puerto"
  else
    echo "HEALTH_FALLO $puerto"
    fallos=$((fallos + 1))
  fi
done
exit "$fallos"
