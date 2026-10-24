"""Checkout: una reserva rechazada no debe crear ni guardar el pedido.

Se ejecuta la ruta real `/api/pedidos/crear` con el cliente de pruebas de
Flask y se sustituyen las dependencias externas (catalogo y base de datos)
para aislar la fase de reserva de stock.
"""
import sys
import hashlib
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))

import app as gateway  # noqa: E402


class _Producto:
    id = 7
    nombre = "Producto de prueba"
    precio = 10.0
    precio_oferta = None


class _ConsultaProducto:
    @staticmethod
    def get(producto_id):
        return _Producto() if int(producto_id) == _Producto.id else None


class _ProductoFalso:
    query = _ConsultaProducto()


def _payload():
    return {
        "clave_idempotencia": "checkout-test-123456",
        "items": [{"id": 7, "cantidad": 2, "nombre": "Nombre del navegador"}],
        "cliente": {
            "nombres": "Ana",
            "apellidos": "Perez",
            "email": "ana@example.test",
            "telefono": "999999999",
            "documento": "12345678",
        },
        "tipo_entrega": "recojo",
        "direccion": "",
        "metodo_pago": "efectivo",
        "comprobante": {"tipo": "boleta"},
    }


@pytest.mark.parametrize(
    ("codigo", "estado_http"),
    [("stock_insuficiente", 409), ("inventario_no_disponible", 503)],
)
def test_reserva_rechazada_no_crea_pedido(monkeypatch, codigo, estado_http):
    creados = []
    liberados = []

    class _ConsultaPedido:
        @staticmethod
        def filter_by(**kwargs):
            return _ConsultaPedido()

        @staticmethod
        def first():
            return None

    with gateway.app.app_context():
        monkeypatch.setattr(gateway.Pedido, "query", _ConsultaPedido())
    monkeypatch.setattr(gateway, "preparar_outbox", lambda bind: True)
    monkeypatch.setattr(gateway, "Producto", _ProductoFalso)
    monkeypatch.setattr(gateway, "_asegurar_cliente_en_principal",
                        lambda cliente_id: None)
    monkeypatch.setattr(gateway, "_punto_entrega_pedido",
                        lambda *a, **k: (None, None, None))
    monkeypatch.setattr(
        gateway, "reservar_stock",
        lambda *a, **k: {"ok": False, "codigo": codigo, "error": "sin stock"},
    )
    monkeypatch.setattr(gateway.db.session, "add",
                        lambda obj: creados.append(obj))
    monkeypatch.setattr(
        gateway, "liberar_stock",
        lambda referencia: liberados.append(referencia) or {"ok": True},
    )

    cliente = gateway.app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["cliente_id"] = 1

    respuesta = cliente.post("/api/pedidos/crear", json=_payload())

    assert respuesta.status_code == estado_http
    cuerpo = respuesta.get_json()
    assert cuerpo["success"] is False
    assert cuerpo["codigo"] == codigo
    # No se agrego ningun Pedido a la sesion y no habia reserva que liberar.
    assert creados == []
    assert liberados == []


def test_reintento_con_misma_clave_y_payload_devuelve_pedido_existente(monkeypatch):
    payload = _payload()
    huella = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    existente = type("PedidoExistente", (), {
        "cliente_id": 1, "huella_idempotencia": huella, "id": 321,
    })()

    class _ConsultaPedido:
        def filter_by(self, **kwargs):
            assert kwargs == {"clave_idempotencia": payload["clave_idempotencia"]}
            return self

        def first(self):
            return existente

    with gateway.app.app_context():
        monkeypatch.setattr(gateway.Pedido, "query", _ConsultaPedido())
    monkeypatch.setattr(gateway, "reservar_stock",
                        lambda *a, **k: pytest.fail("no debe reservar otra vez"))
    cliente = gateway.app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["cliente_id"] = 1

    respuesta = cliente.post(
        "/api/pedidos/crear", json=payload,
        headers={"Idempotency-Key": payload["clave_idempotencia"]})
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "success": True, "duplicado": True, "pedido_id": 321}


def test_reutilizar_clave_con_payload_distinto_se_rechaza(monkeypatch):
    payload = _payload()
    existente = type("PedidoExistente", (), {
        "cliente_id": 1, "huella_idempotencia": "distinta", "id": 321,
    })()

    class _ConsultaPedido:
        def filter_by(self, **kwargs):
            return self

        def first(self):
            return existente

    with gateway.app.app_context():
        monkeypatch.setattr(gateway.Pedido, "query", _ConsultaPedido())
    cliente = gateway.app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["cliente_id"] = 1

    respuesta = cliente.post(
        "/api/pedidos/crear", json=payload,
        headers={"Idempotency-Key": payload["clave_idempotencia"]})
    assert respuesta.status_code == 409
    assert respuesta.get_json()["codigo"] == "clave_idempotencia_reutilizada"
