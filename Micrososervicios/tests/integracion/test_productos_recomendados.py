"""Regresión para recomendaciones que agregan la copia local de ventas."""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))

import app as gateway  # noqa: E402

pytestmark = pytest.mark.integracion


def test_recomendados_no_duplica_la_tabla_ventas(capfd):
    respuesta = gateway.app.test_client().get("/api/productos/recomendados")

    assert respuesta.status_code == 200
    assert isinstance(respuesta.get_json(), list)
    salida = capfd.readouterr()
    assert "Not unique table/alias: 'ventas'" not in salida.out
    assert "Error en /api/productos/recomendados" not in salida.out
