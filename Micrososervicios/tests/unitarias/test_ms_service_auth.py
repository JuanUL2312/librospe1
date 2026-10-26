"""Las APIs de los microservicios no deben aceptar lecturas p?blicas."""
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SERVICIOS = [
    ("inventario", "servicio-inventario/app.py", "/productos"),
    ("ventas", "servicio-ventas/app.py", "/pedidos"),
    ("usuarios", "servicio-usuarios/app.py", "/roles"),
    ("clientes", "servicio-clientes/app.py", "/"),
]


@pytest.fixture(params=SERVICIOS, ids=[x[0] for x in SERVICIOS])
def servicio(request, monkeypatch):
    nombre, ruta, privada = request.param
    monkeypatch.setenv("SERVICE_TOKEN", "pytest-service-token")
    spec = importlib.util.spec_from_file_location(
        f"ms_auth_{nombre}", RAIZ / ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo, privada


def test_ruta_privada_rechaza_sin_token(servicio):
    modulo, ruta = servicio
    respuesta = modulo.app.test_client().get(ruta)
    assert respuesta.status_code == 401
    assert respuesta.get_json() == {"error": "Token de servicio invalido"}


def test_servicio_sin_token_configurado_falla_cerrado(servicio, monkeypatch):
    modulo, ruta = servicio
    monkeypatch.setattr(modulo, "SERVICE_TOKEN", "")
    respuesta = modulo.app.test_client().get(ruta)
    assert respuesta.status_code == 503
    assert respuesta.get_json() == {"error": "Servicio sin token configurado"}


def test_health_sigue_publico(servicio, monkeypatch):
    modulo, _ = servicio

    class Resultado:
        def scalar(self):
            return 0

    monkeypatch.setattr(modulo.db.session, "execute", lambda *a, **k: Resultado())
    respuesta = modulo.app.test_client().get("/health")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["status"] == "OK"
