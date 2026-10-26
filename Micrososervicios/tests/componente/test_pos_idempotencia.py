"""Validacion HTTP de la clave obligatoria del POS heredado."""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))


@pytest.fixture
def cliente_pos():
    os.environ.setdefault("OUTBOX_WORKER", "1")
    import app as gateway_app
    cliente = gateway_app.app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = 12345
    return cliente


def test_pos_rechaza_venta_sin_clave_idempotente(cliente_pos):
    respuesta = cliente_pos.post("/api/ventas/rapida", json={
        "items": [{"id": 1, "cantidad": 1}],
    })
    assert respuesta.status_code == 400
    assert "clave de idempotencia" in respuesta.get_json()["error"]


def test_pos_rechaza_claves_distintas_en_cuerpo_y_cabecera(cliente_pos):
    respuesta = cliente_pos.post("/api/ventas/rapida", json={
        "clave_idempotencia": "pos-test-key-1",
        "items": [{"id": 1, "cantidad": 1}],
    }, headers={"Idempotency-Key": "pos-test-key-2"})
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"] == "Claves de idempotencia no coinciden"


@pytest.mark.parametrize("cantidad", [0, -1, 1.5, True, "1.5"])
def test_pos_rechaza_cantidades_invalidas_antes_de_reservar(cliente_pos, cantidad):
    respuesta = cliente_pos.post("/api/ventas/rapida", json={
        "clave_idempotencia": "pos-invalid-quantity",
        "items": [{"id": 1, "cantidad": cantidad}],
    })
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"] == "Cantidad o producto invalido"
