"""Fixtures compartidas de la suite pytest de LibrosPE.

Los fixtures `servicios` y `gateway` levantan los procesos que falten
(microservicios en 8001-8004 y app_api en 8000) y solo detienen los que
ellos arrancaron; si ya estaban corriendo (run_all.bat, iniciar_servicios_api.sh)
se reutilizan.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

RAIZ = Path(__file__).resolve().parent.parent
PY = sys.executable
for _extra in (RAIZ, RAIZ / "www"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

SERVICIOS = [
    ("inventario", RAIZ / "servicio-inventario", 8001),
    ("ventas", RAIZ / "servicio-ventas", 8002),
    ("usuarios", RAIZ / "servicio-usuarios", 8003),
    ("clientes", RAIZ / "servicio-clientes", 8004),
]

USUARIO_PYTEST = {
    "correo": "pytest-admin@librospe.test",
    "nombres": "Pytest",
    "apellidos": "Admin",
    "clave": "PytestAdmin#2026",
    "rol": "admin",
}


def leer_env():
    env = {}
    archivo = RAIZ / ".env"
    if archivo.is_file():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def salud(url, segundos=2):
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(0.4)
    return None


def borrar_fila(base, tabla, columna, valor, env):
    import pymysql
    conn = pymysql.connect(
        host=env.get("DB_HOST"), user=env.get("DB_USER"),
        password=env.get("DB_PASSWORD"), database=base, connect_timeout=10)
    try:
        with conn.cursor() as cur:
            n = cur.execute(
                f"DELETE FROM {tabla} WHERE {columna} = %s", (valor,))
        conn.commit()
        return n
    finally:
        conn.close()


@pytest.fixture(scope="session")
def env_prueba():
    return leer_env()


@pytest.fixture(scope="session")
def servicios():
    (RAIZ / "logs").mkdir(exist_ok=True)
    subidos = []
    try:
        for nombre, carpeta, puerto in SERVICIOS:
            if salud(f"http://127.0.0.1:{puerto}/health", 1.5) is None:
                log = open(RAIZ / "logs" / f"pytest_{nombre}.log", "w",
                           encoding="utf-8")
                codigo = ("from app import app; "
                          f"app.run(host='127.0.0.1', port={puerto})")
                proc = subprocess.Popen([PY, "-c", codigo], cwd=str(carpeta),
                                        stdout=log, stderr=subprocess.STDOUT)
                subidos.append((nombre, proc))
        for nombre, _, puerto in SERVICIOS:
            r = salud(f"http://127.0.0.1:{puerto}/health", 45)
            assert r is not None, (
                f"el microservicio {nombre} (:{puerto}) no respondio; "
                f"revisa logs/pytest_{nombre}.log")
        yield
    finally:
        for _, proc in subidos:
            proc.terminate()
        if subidos:
            time.sleep(1)
            for _, proc in subidos:
                if proc.poll() is None:
                    proc.kill()


@pytest.fixture(scope="session")
def gateway(servicios):
    (RAIZ / "logs").mkdir(exist_ok=True)
    proc = None
    if salud("http://127.0.0.1:8000/api/health", 1.5) is None:
        log = open(RAIZ / "logs" / "pytest_gateway.log", "w", encoding="utf-8")
        proc = subprocess.Popen([PY, "app_api.py"], cwd=str(RAIZ / "www"),
                                stdout=log, stderr=subprocess.STDOUT)
    assert salud("http://127.0.0.1:8000/api/health", 45) is not None, \
        "el gateway (8000) no respondio; revisa logs/pytest_gateway.log"
    yield "http://127.0.0.1:8000"
    if proc:
        proc.terminate()
        time.sleep(0.5)
        if proc.poll() is None:
            proc.kill()


@pytest.fixture(scope="session")
def admin_jwt(gateway, env_prueba):
    """Usuario admin de prueba (fila temporal) + JWT del gateway."""
    token_interno = {"X-Service-Token": env_prueba.get("SERVICE_TOKEN", "")}
    r = requests.post("http://127.0.0.1:8003/", json=USUARIO_PYTEST,
                      headers=token_interno, timeout=15)
    assert r.status_code in (201, 409), (
        f"no se pudo crear el usuario de prueba: HTTP {r.status_code} "
        f"{r.text[:120]}")
    r = requests.post(
        f"{gateway}/api/v1/auth/login",
        json={"tipo": "usuario", "correo": USUARIO_PYTEST["correo"],
              "clave": USUARIO_PYTEST["clave"]},
        timeout=15)
    assert r.status_code == 200, (
        f"login admin fallo: HTTP {r.status_code} {r.text[:150]}")
    yield {"Authorization": "Bearer " + r.json()["token"]}
    try:
        borrar_fila(env_prueba.get("MS_USUARIOS_DB", "librospe_ms_usuarios"),
                    "usuarios_sistema", "correo", USUARIO_PYTEST["correo"],
                    env_prueba)
    except Exception as e:
        print(f"[pytest] limpieza del usuario de prueba omitida: {e}")
