"""Sustituye ~/iniciar_servicios_api.sh por la versión con esperas y lo ejecuta."""
import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko

SH = r'''#!/bin/bash
# Idempotente: espera la salud de cada microservicio; solo lo lanza si tras
# esperar sigue sin responder. Pensado para cron (panel) o ejecucion manual.
PY="$HOME/www/venv/bin/python"
LOG="$HOME/logs/api_servicios.log"
mkdir -p "$HOME/logs"

salud_ok() {
  "$PY" -c "import urllib.request as u; u.urlopen('http://127.0.0.1:$1/health', timeout=3)" >/dev/null 2>&1
}

for s in servicio-inventario:8001 servicio-ventas:8002 servicio-usuarios:8003 servicio-clientes:8004; do
  nombre="${s%%:*}"
  puerto="${s##*:}"
  if salud_ok "$puerto"; then
    echo "ya arriba $nombre (:$puerto)"
    continue
  fi
  # Si hay procesos app.py (arranque ajeno), esperar su salud antes de duplicar.
  if pgrep -f "venv/bin/python app.py" >/dev/null 2>&1; then
    for i in $(seq 1 20); do
      salud_ok "$puerto" && break
      sleep 2
    done
    if salud_ok "$puerto"; then echo "ya arriba $nombre (:$puerto)"; continue; fi
  fi
  (
    cd "$HOME/$nombre" || exit 1
    nohup "$PY" app.py </dev/null >> "$HOME/logs/$nombre.out" 2>&1 &
    echo "$(date -Is) iniciado $nombre (:$puerto) pid $!" >> "$LOG"
  )
  ok=no
  for i in $(seq 1 30); do
    salud_ok "$puerto" && { ok=si; break; }
    sleep 2
  done
  if [ "$ok" = si ]; then echo "HEALTH_OK $puerto"; else echo "HEALTH_FALLO $puerto"; fi
done
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("ssh-librospe.alwaysdata.net", username="librospe",
          key_filename=os.path.expanduser("~/.ssh/id_ed25519"), timeout=60)

sftp = c.open_sftp()
with sftp.file("/home/librospe/iniciar_servicios_api.sh", "w") as f:
    f.write(SH)
sftp.close()
print("script actualizado")

i, o, e = c.exec_command("chmod +x ~/iniciar_servicios_api.sh && bash ~/iniciar_servicios_api.sh",
                         timeout=300)
out = o.read().decode("utf-8", "replace")
err = e.read().decode("utf-8", "replace").strip()
rc = o.channel.recv_exit_status()
print(out)
if err:
    print("stderr:", err[:400])
print("rc =", rc)
c.close()
sys.exit(rc)
