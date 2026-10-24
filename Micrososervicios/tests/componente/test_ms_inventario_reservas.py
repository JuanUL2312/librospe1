"""Contrato HTTP de las operaciones de reserva del microservicio inventario.

Se ejecuta el endpoint real (test_client) contra MySQL: valida token interno,
descuento unico, idempotencia, rechazo por stock y compensacion.
"""
import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))


@pytest.fixture(scope="module")
def inventario():
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("MS_CONSUMIDOR", "0")
        ruta = RAIZ / "servicio-inventario" / "app.py"
        spec = importlib.util.spec_from_file_location(
            "ms_inventario_reservas", ruta)
        modulo = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(modulo)
            with modulo.app.app_context():
                with modulo.db.engine.connect() as con:
                    con.execute(text("SELECT 1 FROM inventario_productos LIMIT 1"))
        except Exception as e:  # pragma: no cover - depende del entorno
            pytest.skip(f"MySQL de inventario no disponible: {str(e)[:120]}")
        yield modulo


@pytest.fixture
def producto(inventario):
    nombre = f"TEST-HTTP-{uuid.uuid4().hex[:10]}"
    with inventario.app.app_context():
        with inventario.db.engine.begin() as con:
            con.execute(
                text(
                    "INSERT INTO inventario_productos (nombre, cantidad, precio, estado) "
                    "VALUES (:n, 10, 1.00, 1)"
                ),
                {"n": nombre},
            )
            pid = con.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    yield pid
    with inventario.app.app_context():
        with inventario.db.engine.begin() as con:
            con.execute(text("DELETE FROM reservas_stock WHERE producto_id=:p"),
                        {"p": pid})
            con.execute(text("DELETE FROM inventario_productos WHERE id=:p"), {"p": pid})


def _stock(inventario, pid):
    with inventario.app.app_context():
        with inventario.db.engine.connect() as con:
            return con.execute(
                text("SELECT cantidad FROM inventario_productos WHERE id=:p"), {"p": pid}
            ).scalar()


def _post(inventario, ruta, payload, token=True):
    cabeceras = {}
    if token:
        cabeceras["X-Service-Token"] = inventario.SERVICE_TOKEN
    return inventario.app.test_client().post(ruta, json=payload,
                                             headers=cabeceras)


def _ref(prefijo):
    return f"{prefijo}-{uuid.uuid4().hex}"


def test_reserva_exige_token_interno(inventario, producto):
    respuesta = _post(
        inventario, "/_reservar-stock",
        {"referencia": _ref("auth"), "items": [{"id": producto, "cantidad": 1}]},
        token=False,
    )
    assert respuesta.status_code == 401
    assert _stock(inventario, producto) == 10


def test_reserva_descuenta_una_sola_vez(inventario, producto):
    referencia = _ref("ok")
    items = [{"id": producto, "cantidad": 3}]

    primera = _post(inventario, "/_reservar-stock",
                    {"referencia": referencia, "items": items})
    segunda = _post(inventario, "/_reservar-stock",
                    {"referencia": referencia, "items": items})

    assert primera.status_code == 200, primera.get_json()
    assert primera.get_json()["duplicado"] is False
    assert segunda.status_code == 200
    assert segunda.get_json()["duplicado"] is True
    assert _stock(inventario, producto) == 7


def test_reserva_rechaza_stock_insuficiente(inventario, producto):
    with inventario.app.app_context():
        with inventario.db.engine.begin() as con:
            con.execute(text("UPDATE inventario_productos SET cantidad=2 WHERE id=:p"),
                        {"p": producto})

    respuesta = _post(inventario, "/_reservar-stock",
                      {"referencia": _ref("sin"),
                       "items": [{"id": producto, "cantidad": 5}]})

    assert respuesta.status_code == 409
    assert respuesta.get_json()["codigo"] == "stock_insuficiente"
    assert _stock(inventario, producto) == 2


def test_confirmar_y_liberar_no_duplican_efectos(inventario, producto):
    referencia = _ref("ciclo")
    items = [{"id": producto, "cantidad": 3}]
    assert _post(inventario, "/_reservar-stock",
                 {"referencia": referencia, "items": items}).status_code == 200
    confirmada = _post(inventario, "/_confirmar-stock",
                       {"referencia": referencia, "documento_tipo": "pedido",
                        "documento_id": 55})
    assert confirmada.status_code == 200
    assert _stock(inventario, producto) == 7

    duplicada = _post(inventario, "/_reservar-stock",
                      {"referencia": referencia, "items": items})
    assert duplicada.status_code == 200
    assert duplicada.get_json()["estado"] == "confirmado"
    assert duplicada.get_json()["documento_id"] == 55

    # Un pedido confirmado no se compensa.
    _post(inventario, "/_liberar-stock", {"referencia": referencia})
    assert _stock(inventario, producto) == 7


def test_liberar_restaura_una_reserva_pendiente(inventario, producto):
    referencia = _ref("lib")
    items = [{"id": producto, "cantidad": 4}]
    assert _post(inventario, "/_reservar-stock",
                 {"referencia": referencia, "items": items}).status_code == 200
    assert _stock(inventario, producto) == 6

    primera = _post(inventario, "/_liberar-stock", {"referencia": referencia})
    segunda = _post(inventario, "/_liberar-stock", {"referencia": referencia})

    assert primera.status_code == 200
    assert primera.get_json()["liberadas"] == 1
    assert segunda.status_code == 200
    assert segunda.get_json()["liberadas"] == 0
    assert _stock(inventario, producto) == 10


def test_payload_invalido_no_toca_la_base(inventario, producto):
    respuesta = _post(inventario, "/_reservar-stock",
                      {"referencia": "corta", "items": [{"id": producto,
                                                          "cantidad": 1}]})
    assert respuesta.status_code == 400
    assert _stock(inventario, producto) == 10


def test_reserva_concurrente_no_vende_mas_que_el_stock(inventario, producto):
    with inventario.app.app_context():
        with inventario.db.engine.begin() as con:
            con.execute(text("UPDATE inventario_productos SET cantidad=5 WHERE id=:p"),
                        {"p": producto})

    referencias = [_ref("race1"), _ref("race2")]
    def comprar(referencia):
        respuesta = _post(
            inventario, "/_reservar-stock",
            {"referencia": referencia,
             "items": [{"id": producto, "cantidad": 4}]})
        return respuesta.status_code, respuesta.get_json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(comprar, referencias))

    assert sum(1 for status, body in resultados
               if status == 200 and body["ok"]) == 1
    assert sum(1 for status, body in resultados
               if status == 409 and not body["ok"]) == 1
    assert _stock(inventario, producto) == 1


def test_clave_reserva_no_se_reutiliza_con_otro_carrito(inventario, producto):
    referencia = _ref("reuse")
    primera = _post(inventario, "/_reservar-stock",
                    {"referencia": referencia,
                     "items": [{"id": producto, "cantidad": 2}]})
    segunda = _post(inventario, "/_reservar-stock",
                    {"referencia": referencia,
                     "items": [{"id": producto, "cantidad": 3}]})

    assert primera.status_code == 200
    assert segunda.status_code == 409
    assert segunda.get_json()["codigo"] == "clave_idempotencia_reutilizada"
    assert _stock(inventario, producto) == 8
