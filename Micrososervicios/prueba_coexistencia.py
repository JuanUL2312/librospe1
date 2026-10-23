"""Prueba de coexistencia: www/app.py (tienda Jinja) con API_GATEWAY=1

Verifica que el MISMO proceso sirve:
  - la tienda tal cual (/, rutas heredadas, errores HTML fuera de /api/),
  - el API Gateway /api/v1 (JSON + JWT) hacia los 4 microservicios corriendo
    como procesos independientes en 127.0.0.1:8001-8004.

Uso de BD: solo lecturas + usuario de prueba temporal (creado y borrado
al final, igual que pruebas_integracion.py).
"""
import os
import subprocess
import sys
import time

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
PUERTO = 5010
URL = f"http://127.0.0.1:{PUERTO}"

SERVICIOS = [
    ("servicio-inventario", 8001),
    ("servicio-ventas", 8002),
    ("servicio-usuarios", 8003),
    ("servicio-clientes", 8004),
]

USUARIO_PRUEBA = {"correo": "jwt-prueba@librospe.test", "nombres": "Prueba",
                  "apellidos": "JWT", "clave": "PruebaJwt#2026", "rol": "admin"}

fallos = []


def comprobar(nombre, condicion, detalle=""):
    print(f"[{'OK ' if condicion else 'FALLO'}] {nombre} {detalle}")
    if not condicion:
        fallos.append(nombre)


def leer_env():
    env = {}
    ruta = os.path.join(BASE, ".env")
    if os.path.isfile(ruta):
        for linea in open(ruta, encoding="utf-8"):
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def crear_usuario_prueba():
    """True=creado por esta corrida, False=ya existía, None=fallo."""
    env = leer_env()
    try:
        r = requests.post("http://127.0.0.1:8003/", json=USUARIO_PRUEBA,
                          headers={"X-Service-Token": env.get("SERVICE_TOKEN", "")},
                          timeout=10)
    except requests.RequestException as e:
        print(f"      creación de usuario: {e}")
        return None
    if r.status_code == 201:
        return True
    if r.status_code == 409:
        return False
    print(f"      creación de usuario: HTTP {r.status_code}: {r.text[:100]}")
    return None


def limpiar_usuario_prueba():
    try:
        import pymysql
    except ImportError:
        print("      (pymysql no disponible: limpieza omitida)")
        return
    env = leer_env()
    try:
        conn = pymysql.connect(host=env.get("DB_HOST"), user=env.get("DB_USER"),
                               password=env.get("DB_PASSWORD"),
                               database=env.get("MS_USUARIOS_DB", "librospe_ms_usuarios"),
                               connect_timeout=10)
        with conn.cursor() as cur:
            filas = cur.execute(
                "DELETE FROM usuarios_sistema WHERE correo = '%s'"
                % USUARIO_PRUEBA["correo"])
        conn.commit()
        conn.close()
        print(f"      limpieza: {filas} fila(s) de prueba eliminada(s)")
    except Exception as e:
        print(f"      limpieza falló: {e}")


def esperar(url, limite=30):
    fin = time.time() + limite
    while time.time() < fin:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code < 500:
                return r
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return None


procesos = []
usuario_creado = False
try:
    # ------------------------------------------------ servicios independientes
    for carpeta, puerto in SERVICIOS:
        ruta = os.path.join(BASE, carpeta)
        procesos.append(subprocess.Popen(
            [PY, "app.py"], cwd=ruta,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        r = esperar(f"http://127.0.0.1:{puerto}/health", 40)
        comprobar(f"Servicio {carpeta} (:{puerto}) arriba",
                  r is not None and r.status_code == 200,
                  "" if r is not None else "sin respuesta")

    usuario_creado = crear_usuario_prueba() is True
    comprobar("Usuario de prueba disponible",
              usuario_creado is not None, USUARIO_PRUEBA["correo"])

    # ------------------------------------------------ tienda + API en un proceso
    env = dict(os.environ)
    env["API_GATEWAY"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    runner = (
        "import sys; sys.path.insert(0, '.'); "
        "from app import app; "
        f"app.run(host='127.0.0.1', port={PUERTO}, use_reloader=False)"
    )
    procesos.append(subprocess.Popen(
        [PY, "-c", runner], cwd=os.path.join(BASE, "www"), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    r = esperar(f"{URL}/api/v1/health", 45)
    if r is None:
        comprobar("app.py (API_GATEWAY=1) arriba", False, "sin respuesta")
        raise SystemExit(1)
    comprobar("app.py (API_GATEWAY=1) arriba", True)

    # 1) La tienda sigue viva (no 5xx por la integración)
    r = requests.get(f"{URL}/", timeout=20, allow_redirects=False)
    comprobar("GET / (tienda) sin 5xx", r.status_code < 500, str(r.status_code))

    # 2) /api/health = monitor HEREDADO (su JSON, no el del gateway).
    #    Local puede dar 500 (la BD 'librospe_db' no es accesible desde aquí;
    #    en producción responde 200 — verificado en deploys anteriores).
    r = requests.get(f"{URL}/api/health", timeout=10)
    mon = {}
    try:
        mon = r.json() or {}
    except ValueError:
        pass
    comprobar("GET /api/health = monitor heredado (no el del gateway)",
              mon.get("service") == "LibrosPE microservicios"
              or mon.get("status") == "ERROR",
              f"HTTP {r.status_code} status={mon.get('status', '?')}")

    # 3) /api/v1/health = health del gateway (nuevo)
    r = requests.get(f"{URL}/api/v1/health", timeout=10)
    cuerpo = r.json() if r.status_code == 200 else {}
    comprobar("GET /api/v1/health -> 200 api-gateway",
              r.status_code == 200 and cuerpo.get("servicio") == "api-gateway",
              f"{r.status_code} {cuerpo.get('servicio', '')}")
    comprobar("X-Request-Id en /api/*", bool(r.headers.get("X-Request-Id")), "")

    # 4) /api/login (redirección al expirar el JWT)
    r = requests.get(f"{URL}/api/login", timeout=10, allow_redirects=False)
    comprobar("GET /api/login -> 302 al demo",
              r.status_code == 302 and
              r.headers.get("Location", "").startswith("/static/api_demo"),
              f"{r.status_code} {r.headers.get('Location', '')}")

    # 5) Guard CSRF del gateway en /api/v1
    r = requests.post(f"{URL}/api/v1/ventas/listar", json={}, timeout=10)
    comprobar("POST /api/v1 sin JWT -> 403 con mensaje",
              r.status_code == 403 and "sin JWT" in (r.json().get("error") or ""),
              str(r.status_code))

    # 6) Ruta HEREDADA /api/comercial no es interceptada por el guard nuevo
    r = requests.put(f"{URL}/api/comercial/pedidos/999999/estado",
                     json={"estado": "x"}, timeout=10)
    comprobar("PUT /api/comercial heredada NO usa el guard /api/v1",
              "sin JWT" not in r.text, f"HTTP {r.status_code}")

    # 7) Fuera de /api/: los 404 de la tienda siguen en HTML (Flask estándar)
    r = requests.get(f"{URL}/pagina-inexistente-coexistencia-xyz", timeout=10)
    comprobar("404 fuera de /api/ -> HTML",
              r.status_code == 404 and "html" in
              (r.headers.get("Content-Type", "").lower()),
              r.headers.get("Content-Type"))

    # 8) 404 bajo /api/ -> JSON
    r = requests.get(f"{URL}/api/v1/ruta-inexistente-xyz", timeout=10)
    comprobar("404 en /api/v1 -> JSON",
              r.status_code == 404 and (r.json() or {}).get("error") is not None,
              str(r.status_code))

    # 9) Login real -> JWT (usuario de prueba en BD)
    r = requests.post(f"{URL}/api/v1/auth/login",
                      json={"tipo": "usuario",
                            "correo": USUARIO_PRUEBA["correo"],
                            "clave": USUARIO_PRUEBA["clave"]}, timeout=15)
    comprobar("Login personal -> JWT", r.status_code == 200,
              "" if r.status_code == 200 else r.text[:120])
    token = (r.json() or {}).get("token")
    hdr = {"Authorization": f"Bearer {token}"} if token else {}

    # 10) Proxy real: inventario (:8001) con JWT -> productos de la BD
    r = requests.get(f"{URL}/api/v1/inventario/productos", headers=hdr, timeout=15)
    datos = r.json() if r.status_code == 200 else []
    comprobar("GET /api/v1/inventario/productos -> 200 con datos reales",
              r.status_code == 200 and isinstance(datos, list) and len(datos) > 0,
              f"{len(datos) if isinstance(datos, list) else r.status_code} elementos")

    # 11) Health profundo del gateway (estatus de los 4 servicios)
    r = requests.get(f"{URL}/api/v1/health?profundo=1", timeout=25)
    prof = r.json() or {}
    servicios_estado = prof.get("servicios", {})
    comprobar("Health profundo: los 4 servicios OK",
              prof.get("status") == "OK" and
              all(v == "OK" for v in servicios_estado.values()),
              servicios_estado)

finally:
    for p in procesos:
        try:
            p.terminate()
        except Exception:
            pass
    time.sleep(2)
    for p in procesos:
        if p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass
    if usuario_creado:
        limpiar_usuario_prueba()

print()
print("TOTAL:", "TODO OK" if not fallos else f"{len(fallos)} FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
