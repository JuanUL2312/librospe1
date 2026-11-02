"""Verifica /health de los 4 servicios y estado de procesos en Alwaysdata."""
import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko

REMOTO = r'''
import urllib.request as u
for p in (8001, 8002, 8003, 8004):
    try:
        r = u.urlopen("http://127.0.0.1:%d/health" % p, timeout=8)
        print(p, "->", r.status, r.read()[:90].decode("utf-8", "replace"))
    except Exception as ex:
        print(p, "-> FALLO", ex)
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("ssh-librospe.alwaysdata.net", username="librospe",
          key_filename=os.path.expanduser("~/.ssh/id_ed25519"), timeout=60)

cmd = "~/www/venv/bin/python - <<'PYEOF'\n" + REMOTO + "PYEOF"
i, o, e = c.exec_command(cmd, timeout=90)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace").strip()
if err:
    print("ERR:", err[:400])

i, o, e = c.exec_command(
    "ps aux | grep 'python app.py' | grep -v grep | wc -l; "
    "for p in 8001 8002 8003 8004; do tail -c 300 ~/logs/servicio-*.out 2>/dev/null | grep -c 'Running on' >/dev/null; done; "
    "echo '--- ultimas lineas inventario/ventas ---'; "
    "tail -5 ~/logs/servicio-inventario.out; tail -5 ~/logs/servicio-ventas.out", timeout=60)
print(o.read().decode("utf-8", "replace"))
c.close()
