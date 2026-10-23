"""Pruebas de INTEGRACION: patron Outbox (tabla eventos_pendientes).

Verifica el ciclo completo contra la BD real (librospe_ms_ventas):
guardar -> listar pendientes -> marcar enviado, y limpia sus filas.
Si la BD por defecto no es accesible, el test se omite (skip).
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))

from conftest import borrar_fila  # noqa: E402

pytestmark = pytest.mark.integracion

TIPO = "pytest.outbox"


def test_ciclo_outbox_pendiente_y_enviado(env_prueba):
    mensajeria = pytest.importorskip("mensajeria")
    try:
        guardo = mensajeria.guardar_en_outbox(
            TIPO, {"prueba": 1, "nota": "pytest"}, origen="pytest")
    except Exception as e:  # pragma: no cover - entorno sin BD
        pytest.skip(f"outbox no utilizable: {e}")
    if not guardo:
        pytest.skip("sin acceso a la BD por defecto (outbox no disponible)")
    try:
        pendientes = [e for e in mensajeria.pendientes_outbox(200)
                      if e["tipo"] == TIPO]
        assert pendientes, "el evento no quedo en eventos_pendientes"
        ev = pendientes[0]
        assert ev["intentos"] == 0
        assert "prueba" in ev["datos"]

        # marcar_outbox no devuelve valor: la verificacion es por estado
        mensajeria.marcar_outbox(ev["id"], True)

        tras = [e for e in mensajeria.pendientes_outbox(200)
                if e["id"] == ev["id"]]
        assert not tras, "tras marcarse enviado no debe seguir en la cola"
    finally:
        borrar_fila(env_prueba.get("DB_NAME", "librospe_ms_ventas"),
                    "eventos_pendientes", "tipo", TIPO, env_prueba)
