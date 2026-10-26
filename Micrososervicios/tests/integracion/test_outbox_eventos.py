"""Pruebas de INTEGRACION: backoff y limite de intentos del Outbox."""
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))

from conftest import borrar_fila  # noqa: E402

pytestmark = pytest.mark.integracion

TIPO = "pytest.outbox." + uuid.uuid4().hex


def test_outbox_backoff_reintentos_y_reencolado(env_prueba):
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

        # El fallo aplica backoff; el evento no se vuelve a tomar en el
        # siguiente ciclo hasta que venza proximo_intento.
        mensajeria.marcar_outbox(ev["id"], False, "fallo simulado")
        pendientes_despues_error = [e for e in mensajeria.pendientes_outbox(200)
                                    if e["id"] == ev["id"]]
        assert not pendientes_despues_error
        app, db = mensajeria._db()
        with app.app_context(), db.engine.begin() as con:
            fila = con.execute(
                text("SELECT estado, intentos, proximo_intento FROM eventos_pendientes "
                     "WHERE id=:id"), {"id": ev["id"]}).first()
            assert fila.estado == "pendiente"
            assert fila.intentos == 1
            assert fila.proximo_intento is not None
            con.execute(
                text("UPDATE eventos_pendientes SET proximo_intento=DATE_SUB(NOW(), "
                     "INTERVAL 1 SECOND) WHERE id=:id"), {"id": ev["id"]})
        assert any(e["id"] == ev["id"] for e in mensajeria.pendientes_outbox(200))

        # Diez fallos pasan a estado terminal; no se reintentan sin accion.
        for _ in range(mensajeria.MAX_INTENTOS_OUTBOX - 1):
            mensajeria.marcar_outbox(ev["id"], False, "fallo persistente")
        with app.app_context(), db.engine.connect() as con:
            estado = con.execute(
                text("SELECT estado FROM eventos_pendientes WHERE id=:id"),
                {"id": ev["id"]}).scalar()
        assert estado == "fallido"

        tras = [e for e in mensajeria.pendientes_outbox(200)
                if e["id"] == ev["id"]]
        assert not tras, "tras marcarse enviado no debe seguir en la cola"
        assert mensajeria.reencolar_fallidos(1, tipo=TIPO) == 1
        tras_reencolado = [e for e in mensajeria.pendientes_outbox(200)
                           if e["id"] == ev["id"]]
        assert len(tras_reencolado) == 1
        assert tras_reencolado[0]["intentos"] == 0
    finally:
        borrar_fila(env_prueba.get("DB_NAME", "librospe_ms_ventas"),
                    "eventos_pendientes", "tipo", TIPO, env_prueba)
