"""Pruebas de RESILIENCIA: el gateway ante microservicios caidos.

Valida que una caida de red se traduzca en un 503 controlado (con detalle
y request_id) y NO en un 500 ni en un proceso colgado: el proxy tiene
timeout estricto (3s conexion / 8s lectura) y no reintenta mutantes.
"""
import time

import pytest

pytestmark = pytest.mark.resiliencia


@pytest.fixture
def app_gateway(admin_jwt):
    """App del gateway puro en memoria (no necesita el proceso de :8000).

    Depende de admin_jwt solo para garantizar que el usuario de prueba
    exista (el login de cada test lo necesita).
    """
    import app_api
    return app_api.app


def _login_admin(app):
    from conftest import USUARIO_PYTEST
    cliente = app.test_client()
    r = cliente.post("/api/v1/auth/login", json={
        "tipo": "usuario", "correo": USUARIO_PYTEST["correo"],
        "clave": USUARIO_PYTEST["clave"],
    })
    assert r.status_code == 200, (
        f"login para la prueba de resiliencia fallo: HTTP {r.status_code} "
        f"{r.get_json()}")
    return cliente, {"Authorization": "Bearer " + r.get_json()["token"]}


def _restaurar(app, valor):
    app.config["MS_CLIENTES_URL"] = valor


def test_clientes_caido_responde_503_rapido(app_gateway):
    original = app_gateway.config["MS_CLIENTES_URL"]
    # puerto cerrado en localhost: conexion rechazada al instante
    app_gateway.config["MS_CLIENTES_URL"] = "http://127.0.0.1:59999"
    try:
        cliente, tok = _login_admin(app_gateway)
        t0 = time.time()
        r = cliente.get("/api/v1/clientes/listar", headers=tok)
        demora = time.time() - t0
        assert r.status_code == 503
        cuerpo = r.get_json()
        assert cuerpo["servicio"] == "clientes"
        assert "no disponible" in cuerpo["error"]
        assert cuerpo.get("request_id")
        assert demora < 10, f"demoro {demora:.1f}s: el gateway no debe colgarse"
    finally:
        _restaurar(app_gateway, original)


def test_url_autoreferenciada_se_bloquea_con_503(app_gateway):
    """El escudo anti-autobloqueo: URL del servicio == host del proceso."""
    original = app_gateway.config["MS_CLIENTES_URL"]
    app_gateway.config["MS_CLIENTES_URL"] = "http://localhost"
    try:
        cliente, tok = _login_admin(app_gateway)
        t0 = time.time()
        r = cliente.get("/api/v1/clientes/listar", headers=tok)
        demora = time.time() - t0
        assert r.status_code == 503
        assert "propio proceso" in r.get_json()["detalle"]
        assert demora < 2, "el escudo debe responder sin esperar la red"
    finally:
        _restaurar(app_gateway, original)


def test_servicio_sin_respuesta_genera_503_con_timeout(app_gateway):
    """Host no enrutable: el timeout (3s de conexion) evita hilos colgados."""
    original = app_gateway.config["MS_CLIENTES_URL"]
    app_gateway.config["MS_CLIENTES_URL"] = "http://10.255.255.1:81"
    try:
        cliente, tok = _login_admin(app_gateway)
        t0 = time.time()
        r = cliente.get("/api/v1/clientes/listar", headers=tok)
        demora = time.time() - t0
        assert r.status_code == 503
        assert "timeout" in r.get_json()["detalle"] or \
               "sin conexión" in r.get_json()["detalle"]
        # 2 intentos de GET x 3s de conexion = ~6s; margen holgado
        assert demora < 20, f"demoro {demora:.1f}s: el timeout no esta activo"
    finally:
        _restaurar(app_gateway, original)
