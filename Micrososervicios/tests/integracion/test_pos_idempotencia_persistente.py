"""Comprueba la persistencia y unicidad de claves POS en la BD de ventas."""
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))

pytestmark = pytest.mark.integracion


@pytest.fixture(scope="module")
def ventas_db():
    import os
    os.environ.setdefault("OUTBOX_WORKER", "1")
    import app as gateway_app
    try:
        with gateway_app.app.app_context():
            engine = gateway_app.db.engines["ventas"]
            with engine.connect() as con:
                con.execute(text("SELECT clave FROM pos_ventas_idempotencia LIMIT 1"))
    except Exception as e:  # pragma: no cover - depende del entorno
        pytest.skip(f"Base de ventas o migracion POS no disponible: {str(e)[:120]}")
    return gateway_app, engine


@pytest.fixture
def limpiar_pos(ventas_db):
    _gateway_app, engine = ventas_db
    claves = []
    yield claves
    with engine.begin() as con:
        for clave in claves:
            con.execute(text("DELETE FROM pos_ventas_idempotencia WHERE clave=:k"),
                        {"k": clave})


def test_clave_pos_persiste_tras_nueva_sesion_y_rechaza_duplicado(ventas_db, limpiar_pos):
    _gateway_app, engine = ventas_db
    clave = "pytest-" + uuid.uuid4().hex
    limpiar_pos.append(clave)
    referencia = "pos:" + uuid.uuid4().hex
    respuesta = json.dumps({"success": True, "venta_id": 987654321, "total": 12.5})

    with engine.begin() as con:
        con.execute(text(
            "INSERT INTO pos_ventas_idempotencia "
            "(clave, huella, referencia_stock, respuesta) "
            "VALUES (:k, :h, :r, :p)"),
            {"k": clave, "h": "a" * 64, "r": referencia, "p": respuesta})

    # Una nueva conexión simula un reinicio de proceso: la respuesta no vive
    # únicamente en la memoria del Gateway.
    with engine.connect() as con:
        fila = con.execute(text(
            "SELECT huella, respuesta, stock_confirmado "
            "FROM pos_ventas_idempotencia WHERE clave=:k"), {"k": clave}).first()
    assert fila.huella == "a" * 64
    assert json.loads(fila.respuesta)["venta_id"] == 987654321
    assert not fila.stock_confirmado

    with pytest.raises(IntegrityError):
        with engine.begin() as con:
            con.execute(text(
                "INSERT INTO pos_ventas_idempotencia "
                "(clave, huella, referencia_stock, respuesta) "
                "VALUES (:k, :h, :r, :p)"),
                {"k": clave, "h": "a" * 64, "r": referencia, "p": respuesta})



def test_dos_sesiones_no_pueden_confirmar_la_misma_clave(ventas_db, limpiar_pos):
    _gateway_app, engine = ventas_db
    clave = "race-" + uuid.uuid4().hex
    limpiar_pos.append(clave)
    referencia = "pos:" + uuid.uuid4().hex
    barrera = __import__("threading").Barrier(2)
    respuesta = json.dumps({"success": True, "venta_id": 987654322, "total": 1.0})

    def insertar():
        barrera.wait()
        try:
            with engine.begin() as con:
                con.execute(text(
                    "INSERT INTO pos_ventas_idempotencia "
                    "(clave, huella, referencia_stock, respuesta) "
                    "VALUES (:k, :h, :r, :p)"),
                    {"k": clave, "h": "b" * 64, "r": referencia, "p": respuesta})
            return "insertado"
        except IntegrityError:
            return "duplicado"

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda _: insertar(), range(2)))
    assert sorted(resultados) == ["duplicado", "insertado"]

    with engine.begin() as con:
        assert con.execute(text(
            "SELECT COUNT(*) FROM pos_ventas_idempotencia WHERE clave=:k"),
            {"k": clave}).scalar() == 1
