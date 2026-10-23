"""Pruebas de COMPONENTE: el microservicio de INVENTARIO con test_client.

Aislado del gateway y de RabbitMQ; solo lecturas sobre su BD real.
"""
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.componente


def _app_inventario():
    ruta = RAIZ / "servicio-inventario" / "app.py"
    spec = importlib.util.spec_from_file_location(
        "ms_inventario_componente", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app


def test_lecturas_aisladas(env_prueba):
    app = _app_inventario()
    cliente = app.test_client()
    token = {"X-Service-Token": env_prueba.get("SERVICE_TOKEN", "")}

    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.get_json()["servicio"] == "inventario"

    prods = cliente.get("/productos").get_json()
    assert isinstance(prods, list) and prods
    assert {"id", "nombre", "precio"} <= set(prods[0])

    assert cliente.get("/productos/999999").status_code == 404

    # variante publica y protegida de verificacion de stock
    r = cliente.get("/verificar-stock/1/1")
    assert r.status_code == 200
    assert isinstance(r.get_json()["disponible"], bool)

    r = cliente.get("/_verificar-stock/1/1")
    assert r.status_code == 401
    r = cliente.get("/_verificar-stock/1/1", headers=token)
    assert r.status_code == 200
    d = r.get_json()
    assert d["producto_id"] == 1
    assert d["cantidad_solicitada"] == 1
