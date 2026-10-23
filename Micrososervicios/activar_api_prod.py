"""Fase de activación en Alwaysdata (NO reinicia el sitio de la tienda).

1) Backup de ~/.env y alta de API_GATEWAY=1 + MS_*_URL (127.0.0.1:8001-8004).
2) Sube ~/iniciar_servicios_api.sh (idempotente) y lo ejecuta.
3) Verifica /health de los 4 servicios y que la tienda sigue viva.
"""
import os
import sys
import time

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import paramiko

HOST = "ssh-librospe.alwaysdata.net"
USER = "librospe"
KEY = os.path.expanduser("~/.ssh/id_ed25519")
PUERTOS = [8001, 8002, 8003, 8004]

ACTIVAR_ENV_PY = r'''
import os
env_path = os.path.expanduser("~/.env")
nuevas = {
    "API_GATEWAY": "1",
    "MS_INVENTARIO_URL": "http://127.0.0.1:8001",
    "MS_VENTAS_URL": "http://127.0.0.1:8002",
    "MS_USUARIOS_URL": "http://127.0.0.1:8003",
    "MS_CLIENTES_URL": "http://127.0.0.1:8004",
}
with open(env_path, encoding="utf-8") as f:
    lineas = f.read().splitlines()
salida, vistos = [], set()
for l in lineas:
    s = l.strip()
    if s and not s.startswith("#") and "=" in s:
        k = s.split("=", 1)[0].strip()
        if k in nuevas:
            if k in vistos:
                continue
            salida.append("%s=%s" % (k, nuevas[k]))
            vistos.add(k)
            continue
    salida.append(l)
for k, v in nuevas.items():
    if k not in vistos:
        salida.append("%s=%s" % (k, v))
with open(env_path, "w", encoding="utf-8") as f:
    f.write("\n".join(salida) + "\n")
os.chmod(env_path, 0o600)
print("ENV_OK")
for k in sorted(nuevas):
    print("   %s=%s" % (k, nuevas[k]))
'''

INICIAR_SH = r'''#!/bin/bash
# Idempotente: solo levanta el servicio si /health no responde.
PY="$HOME/www/venv/bin/python"
mkdir -p "$HOME/logs"
for s in servicio-inventario:8001 servicio-ventas:8002 servicio-usuarios:8003 servicio-clientes:8004; do
  nombre="${s%%:*}"
  puerto="${s##*:}"
  if "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$puerto/health', timeout=2)" >/dev/null 2>&1; then
    echo "ya arriba $nombre (:$puerto)"
    continue
  fi
  (
    cd "$HOME/$nombre" || exit 1
    nohup "$PY" app.py </dev/null >> "$HOME/logs/$nombre.out" 2>&1 &
    echo "$(date -Is) iniciado $nombre (:$puerto) pid $!"
  ) >> "$HOME/logs/api_servicios.log"
done
sleep 2
for s in servicio-inventario:8001 servicio-ventas:8002 servicio-usuarios:8003 servicio-clientes:8004; do
  puerto="${s##*:}"
  if "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$puerto/health', timeout=5)" >/dev/null 2>&1; then
    echo "HEALTH_OK $puerto"
  else
    echo "HEALTH_FALLO $puerto"
  fi
done
'''

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, key_filename=KEY, timeout=60)


def ejecutar(cmd, timeout=120, esperar=True):
    print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    if esperar:
        out = stdout.read().decode("utf-8", "replace").strip()
        err = stderr.read().decode("utf-8", "replace").strip()
        rc = stdout.channel.recv_exit_status()
        if out:
            print(out)
        if err:
            print("  [stderr]", err[:500])
        print(f"  -> rc={rc}")
        return rc, out
    return 0, ""


fails = []

# ---------------- 1) backup .env + escribir activador ----------------
rc, _ = ejecutar("ts=$(date +%Y%m%d-%H%M%S); cp -p ~/.env ~/.env.bak-api-$ts && echo BACKUP_OK ~/.env.bak-api-$ts")
if rc != 0:
    fails.append("backup .env")

sftp = client.open_sftp()
sftp.file("/home/librospe/activar_api_env.py", "w").write(ACTIVAR_ENV_PY)
sftp.file("/home/librospe/iniciar_servicios_api.sh", "w").write(INICIAR_SH)
sftp.close()
print("subidos: activar_api_env.py, iniciar_servicios_api.sh")

rc, out = ejecutar("~/www/venv/bin/python ~/activar_api_env.py")
if rc != 0 or "ENV_OK" not in out:
    fails.append("edicion .env")

# ---------------- 2) arrancar servicios ----------------
ejecutar("chmod +x ~/iniciar_servicios_api.sh")
rc, out = ejecutar("bash ~/iniciar_servicios_api.sh", timeout=180)
if "HEALTH_FALLO" in out:
    fails.append("health servicios")

# ---------------- 3) verificaciones independientes ----------------
time.sleep(2)
for puerto in PUERTOS:
    rc, out = ejecutar(
        f'~/www/venv/bin/python -c "import urllib.request as u; '
        f'r=u.urlopen(\'http://127.0.0.1:{puerto}/health\', timeout=6); '
        f'print(r.status, r.read()[:80])"', timeout=30)
    if rc != 0:
        fails.append(f"health {puerto}")

# Tienda actual intacta (sin restart aún)
try:
    import urllib.request
    r = urllib.request.urlopen("https://librospe.alwaysdata.net/api/health", timeout=30)
    print(f"tienda activa: HTTP {r.status}")
    if r.status != 200:
        fails.append("tienda health")
except Exception as e:
    print(f"tienda health: {e}")
    fails.append("tienda health")

client.close()

print()
print("=" * 60)
if fails:
    print("ACTIVACION CON FALLOS:", fails)
else:
    print("PRE-ACTIVACION OK — falta UN paso en el panel:")
    print("  Web > Sites > sitio de la tienda > Restart")
    print("(con API_GATEWAY=1 el proceso app.py servira ademas /api/v1)")
print("=" * 60)
sys.exit(1 if fails else 0)
