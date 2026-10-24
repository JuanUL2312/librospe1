"""Regresiones para autenticacion y validacion del endpoint interno de stock."""
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def inventario(monkeypatch):
    monkeypatch.setenv("MS_CONSUMIDOR", "0")
    ruta = RAIZ / "servicio-inventario" / "app.py"
    spec = importlib.util.spec_from_file_location("ms_inventario_stock_unit", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_actualizar_stock_exige_token_interno(inventario):
    respuesta = inventario.app.test_client().put("/stock/1", json={"cantidad": 3})
    assert respuesta.status_code == 401


@pytest.mark.parametrize("cantidad", [-1, 1.5, True, "abc"])
def test_actualizar_stock_rechaza_cantidad_invalida_sin_consultar_bd(inventario, monkeypatch, cantidad):
    def no_debe_consultar(*args, **kwargs):
        pytest.fail("No se debe acceder a la BD para una cantidad invalida")

    monkeypatch.setattr(inventario.db.session, "execute", no_debe_consultar)
    cliente = inventario.app.test_client()
    respuesta = cliente.put(
        "/stock/1", json={"cantidad": cantidad},
        headers={"X-Service-Token": inventario.SERVICE_TOKEN})
    assert respuesta.status_code == 400


def test_actualizar_stock_autorizado_confirma_el_cambio(inventario, monkeypatch):
    class Resultado:
        rowcount = 1

    llamadas = []
    monkeypatch.setattr(inventario.db.session, "execute",
                        lambda *args, **kwargs: (llamadas.append((args, kwargs)) or Resultado()))
    monkeypatch.setattr(inventario.db.session, "commit", lambda: llamadas.append("commit"))
    cliente = inventario.app.test_client()
    respuesta = cliente.put(
        "/stock/1", json={"cantidad": 0},
        headers={"X-Service-Token": inventario.SERVICE_TOKEN})
    assert respuesta.status_code == 200
    assert llamadas[0][0][1]["c"] == 0
    assert llamadas[-1] == "commit"
