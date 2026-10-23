"""Pruebas de INTEGRACIÓN reales del API Gateway JWT con los 4 microservicios.

Todo-en-uno:
  1) lanza inventario(8001), ventas(8002), usuarios(8003), clientes(8004)
  2) lanza el gateway app_api (8000)
  3) ejecuta los casos contra servicios VIVOS (BD real: SOLO lecturas +
     2 filas de prueba que se eliminan al final)
  4) termina los 6 procesos (incluso si algo falla)

Uso:  .venv-live\\Scripts\\python.exe pruebas_integracion.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent
PY = sys.executable
PUERTO_GATEWAY = 8000
USUARIO_PRUEBA = {"correo": "jwt-prueba@librospe.test", "nombres": "Prueba",
                  "apellidos": "JWT", "clave": "PruebaJwt#2026", "rol": "admin"}
CLIENTE_PRUEBA = {"email": "cliente-jwt-prueba@librospe.test", "nombres": "Cliente",
                  "apellidos": "Prueba", "clave": "PruebaJwt#2026",
                  "departamento": "Junin", "provincia": "Huancayo",
                  "distrito": "Chilca"}

SERVICIOS = [
    ("inventario", RAIZ / "servicio-inventario", 8001),
    ("ventas",     RAIZ / "servicio-ventas",     8002),
    ("usuarios",   RAIZ / "servicio-usuarios",   8003),
    ("clientes",   RAIZ / "servicio-clientes",   8004),
]

procesos = []
fallos = []


def comprobar(nombre, condicion, detalle=""):
    etiqueta = "OK  " if condicion else "FALLO"
    linea = f"[{etiqueta}] {nombre}"
    if detalle:
        linea += f" -> {str(detalle)[:120]}"
    print(linea, flush=True)
    if not condicion:
        fallos.append(nombre)


def leer_env():
    env = {}
    for archivo in (RAIZ / ".env", RAIZ / "www" / ".env"):
        if archivo.is_file():
            for linea in archivo.read_text(encoding="utf-8").splitlines():
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def arrancar(nombre, cwd, args):
    log = open(RAIZ / "logs" / f"prueba_{nombre}.log", "w", encoding="utf-8")
    proc = subprocess.Popen(args, cwd=str(cwd), stdout=log, stderr=subprocess.STDOUT)
    procesos.append(proc)
    return proc


def esperar(url, segundos=40):
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return None


def servicio_token(env):
    return env.get("SERVICE_TOKEN", "")


def main():
    (RAIZ / "logs").mkdir(exist_ok=True)
    env = leer_env()

    # ---------- 1) servicios ----------
    for nombre, carpeta, puerto in SERVICIOS:
        codigo = ("from app import app; "
                  f"app.run(host='127.0.0.1', port={puerto})")
        arrancar(nombre, carpeta, [PY, "-c", codigo])
    for nombre, _, puerto in SERVICIOS:
        r = esperar(f"http://127.0.0.1:{puerto}/health")
        comprobar(f"Servicio {nombre} :{puerto} arriba", r is not None,
                  r.json() if r else "no responde (¿BD inaccesible?)")
        if r is None:
            print("      -> revisar logs/prueba_%s.log" % nombre)
    if fallos:
        return 1

    # ---------- 2) gateway ----------
    arrancar("gateway", RAIZ / "www", [PY, "app_api.py"])
    g = f"http://127.0.0.1:{PUERTO_GATEWAY}"
    r = esperar(f"{g}/api/health")
    comprobar("Gateway arriba", r is not None)
    if r is None:
        return 1
    r = requests.get(f"{g}/api/health?profundo=1", timeout=25)
    servicios_estado = (r.json() or {}).get("servicios", {})
    comprobar("Health profundo: los 4 servicios OK",
              all(v == "OK" for v in servicios_estado.values()), servicios_estado)

    # ---------- 3) usuario de prueba (fila temporal en BD real) ----------
    r = requests.post("http://127.0.0.1:8003/",
                      json=USUARIO_PRUEBA,
                      headers={"X-Service-Token": servicio_token(env)}, timeout=10)
    if r.status_code == 201:
        id_usuario = r.json()["id"]
        comprobar("Usuario de prueba creado (fila temporal)", True, id_usuario)
    elif r.status_code == 409:
        lista = requests.get("http://127.0.0.1:8003/", timeout=10).json()
        id_usuario = next((u["id"] for u in lista
                           if u["correo"] == USUARIO_PRUEBA["correo"]), None)
        comprobar("Usuario de prueba ya existía (reutilizado)", id_usuario is not None,
                  id_usuario)
    else:
        comprobar("Usuario de prueba creado", False, f"HTTP {r.status_code}: {r.text[:80]}")
        return 1

    # ---------- 4) login + lecturas reales con JWT ----------
    r = requests.post(f"{g}/api/v1/auth/login",
                      json={"tipo": "usuario",
                            "correo": USUARIO_PRUEBA["correo"],
                            "clave": USUARIO_PRUEBA["clave"]}, timeout=15)
    comprobar("Login personal -> JWT", r.status_code == 200,
              r.json().get("error", r.json().get("usuario", "")) if r.status_code != 200
              else f"rol={r.json()['usuario']['rol']}")
    if r.status_code != 200:
        return 1
    tok_admin = {"Authorization": "Bearer " + r.json()["token"]}

    r = requests.post(f"{g}/api/v1/auth/login", json={"tipo": "raro"}, timeout=10)
    comprobar("Login con tipo inválido -> 400", r.status_code == 400, r.status_code)

    r = requests.get(f"{g}/api/v1/inventario/productos", headers=tok_admin, timeout=15)
    datos = r.json() if r.status_code == 200 else []
    comprobar("Productos reales con JWT (lectura BD inventario)",
              r.status_code == 200 and isinstance(datos, list) and len(datos) > 0,
              f"{len(datos) if isinstance(datos, list) else '?'} productos")

    r = requests.get(f"{g}/api/v1/usuarios/listar", headers=tok_admin, timeout=15)
    usuarios = r.json() if r.status_code == 200 else []
    comprobar("Usuarios reales con JWT admin",
              r.status_code == 200 and any(
                  u.get("correo") == USUARIO_PRUEBA["correo"] for u in usuarios),
              f"{len(usuarios)} usuarios")

    r = requests.get(f"{g}/api/v1/clientes/listar", headers=tok_admin, timeout=15)
    comprobar("Clientes reales con JWT admin",
              r.status_code == 200 and isinstance(r.json(), list),
              f"{len(r.json())} clientes")

    r = requests.get(f"{g}/api/v1/ventas/listar", headers=tok_admin, timeout=20)
    comprobar("Ventas reales con JWT admin",
              r.status_code == 200 and isinstance(r.json(), list),
              f"{len(r.json())} ventas")

    r = requests.get(f"{g}/api/v1/inventario/stock-bajo/10", headers=tok_admin, timeout=15)
    comprobar("Stock bajo con JWT admin", r.status_code == 200,
              f"HTTP {r.status_code}")

    # ventas/crear con admin pasa el guard de rol pero falla la validación
    # (400) ANTES de tocar la BD: se prueba el rol sin escribir ventas.
    r = requests.post(f"{g}/api/v1/ventas/crear", json={},
                      headers=tok_admin, timeout=10)
    comprobar("ventas/crear admin pasa rol, valida payload -> 400",
              r.status_code == 400, r.status_code)

    # ---------- 5) ciclo completo del CLIENTE de la tienda ----------
    r = requests.post(f"{g}/api/v1/clientes/registro", json=CLIENTE_PRUEBA, timeout=15)
    if r.status_code == 201:
        id_cliente = r.json().get("id")
        comprobar("Registro público de cliente -> 201", True, id_cliente)
    elif r.status_code == 409:
        base = requests.get("http://127.0.0.1:8004/", timeout=10).json()
        id_cliente = next((c["id"] for c in base
                           if c["correo"] == CLIENTE_PRUEBA["email"]), None)
        comprobar("Cliente de prueba ya existía (reutilizado)", id_cliente is not None,
                  id_cliente)
    else:
        comprobar("Registro de cliente", False, f"HTTP {r.status_code}: {r.text[:100]}")
        return 1

    r = requests.post(f"{g}/api/v1/auth/login",
                      json={"tipo": "cliente",
                            "correo": CLIENTE_PRUEBA["email"],
                            "clave": CLIENTE_PRUEBA["clave"]}, timeout=15)
    comprobar("Login cliente de tienda -> JWT rol cliente",
              r.status_code == 200 and r.json()["usuario"]["rol"] == "cliente",
              r.json().get("error", f"rol={r.json().get('usuario', {}).get('rol')}"))
    if r.status_code != 200:
        return 1
    tok_cliente = {"Authorization": "Bearer " + r.json()["token"]}

    r = requests.get(f"{g}/api/v1/clientes/{id_cliente}", headers=tok_cliente, timeout=10)
    comprobar("Cliente ve SU propio registro -> 200", r.status_code == 200, r.status_code)

    r = requests.get(f"{g}/api/v1/clientes/1", headers=tok_cliente, timeout=10)
    comprobar("Cliente NO ve registro ajeno -> 403", r.status_code == 403, r.status_code)

    r = requests.put(f"{g}/api/v1/clientes/{id_cliente}",
                     json={"telefono": "999888777"}, headers=tok_cliente, timeout=10)
    comprobar("Cliente actualiza SU teléfono -> 200", r.status_code == 200, r.status_code)

    r = requests.delete(f"{g}/api/v1/clientes/{id_cliente}", headers=tok_cliente, timeout=10)
    comprobar("Cliente no se elimina -> 403", r.status_code == 403, r.status_code)

    r = requests.get(f"{g}/api/v1/usuarios/listar", headers=tok_cliente, timeout=10)
    comprobar("Cliente sin acceso a usuarios -> 403", r.status_code == 403, r.status_code)

    r = requests.post(f"{g}/api/v1/ventas/crear", json={"producto_id": 1},
                      headers=tok_cliente, timeout=10)
    comprobar("Cliente no puede vender -> 403", r.status_code == 403, r.status_code)

    r = requests.post(f"{g}/api/v1/auth/logout", headers=tok_cliente, timeout=10)
    comprobar("Logout -> 200", r.status_code == 200, r.status_code)

    return 0


def limpiar_bd():
    """Elimina las filas de prueba de la BD real (solo esas)."""
    try:
        import pymysql
    except ImportError:
        print("      (pymysql no disponible: limpieza omitida)")
        return
    env = leer_env()
    conexiones = [
        (env.get("MS_USUARIOS_DB", "librospe_ms_usuarios"),
         f"DELETE FROM usuarios_sistema WHERE correo = '{USUARIO_PRUEBA['correo']}'"),
        (env.get("MS_CLIENTES_DB", "librospe_ms_clientes"),
         f"DELETE FROM clientes WHERE correo = '{CLIENTE_PRUEBA['email']}'"),
    ]
    for base, sql in conexiones:
        try:
            conn = pymysql.connect(
                host=env.get("DB_HOST"), user=env.get("DB_USER"),
                password=env.get("DB_PASSWORD"), database=base,
                connect_timeout=10)
            with conn.cursor() as cur:
                filas = cur.execute(sql)
            conn.commit()
            conn.close()
            print(f"      limpieza {base}: {filas} fila(s) de prueba eliminada(s)")
        except Exception as e:
            print(f"      limpieza {base} falló: {e}")


if __name__ == "__main__":
    try:
        codigo = main()
    finally:
        print("\nDeteniendo procesos...")
        for p in procesos:
            try:
                p.terminate()
            except Exception:
                pass
        time.sleep(1)
        for p in procesos:
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass
        limpiar_bd()
    print()
    print("INTEGRACIÓN:", "TODO OK" if not fallos and codigo == 0
          else f"{len(fallos)} FALLOS: {fallos}")
    sys.exit(codigo or (1 if fallos else 0))
