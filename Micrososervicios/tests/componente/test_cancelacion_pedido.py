"""Pruebas unitarias del estado de cancelacion y su reintento seguro."""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))
import app as gateway  # noqa: E402


class _PedidoQuery:
    def __init__(self, pedido):
        self.pedido = pedido

    def get_or_404(self, pedido_id):
        assert pedido_id == self.pedido.id
        return self.pedido


class _Pedido:
    id = 77
    clave_idempotencia = "cancelacion-test-0001"
    estado = "pendiente"
    metodo_pago = "tarjeta"
    cargo_contraentrega = 0
    tipo_entrega = "recojo"


def _cliente_admin():
    cliente = gateway.app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["rol"] = "administrador"
        sesion["usuario_id"] = 1
    return cliente


def test_cancelar_devuelve_stock_y_persiste_estado_final(monkeypatch):
    pedido = _Pedido()
    commits = []
    devoluciones = []
    with gateway.app.app_context():
        monkeypatch.setattr(gateway.Pedido, "query", _PedidoQuery(pedido))
    monkeypatch.setattr(gateway.db.session, "commit", lambda: commits.append(pedido.estado))
    monkeypatch.setattr(
        gateway, "cancelar_stock_confirmado",
        lambda *args, **kwargs: devoluciones.append((args, kwargs)) or {"ok": True},
    )

    respuesta = _cliente_admin().post(
        "/pedidos/cambiar-estado/77", data={"estado": "cancelado"},
        headers={"X-Requested-With": "XMLHttpRequest"})

    assert respuesta.status_code == 200
    assert pedido.estado == "cancelado"
    assert commits == ["cancelando", "cancelado"]
    assert len(devoluciones) == 1


def test_fallo_de_devolucion_deja_estado_reintentable(monkeypatch):
    pedido = _Pedido()
    commits = []
    resultados = iter([
        {"ok": False, "codigo": "inventario_no_disponible"},
        {"ok": True},
    ])
    with gateway.app.app_context():
        monkeypatch.setattr(gateway.Pedido, "query", _PedidoQuery(pedido))
    monkeypatch.setattr(gateway.db.session, "commit", lambda: commits.append(pedido.estado))
    monkeypatch.setattr(gateway, "cancelar_stock_confirmado",
                        lambda *args, **kwargs: next(resultados))
    cliente = _cliente_admin()

    primera = cliente.post(
        "/pedidos/cambiar-estado/77", data={"estado": "cancelado"},
        headers={"X-Requested-With": "XMLHttpRequest"})
    assert primera.status_code == 503
    assert primera.get_json()["estado"] == "cancelando"
    assert pedido.estado == "cancelando"

    segunda = cliente.post(
        "/pedidos/cambiar-estado/77", data={"estado": "cancelado"},
        headers={"X-Requested-With": "XMLHttpRequest"})
    assert segunda.status_code == 200
    assert pedido.estado == "cancelado"
    assert commits == ["cancelando", "cancelando", "cancelado"]


def test_pedido_enviado_no_reintegra_stock_automaticamente(monkeypatch):
    pedido = _Pedido()
    pedido.estado = "enviado"
    commits = []
    with gateway.app.app_context():
        monkeypatch.setattr(gateway.Pedido, "query", _PedidoQuery(pedido))
    monkeypatch.setattr(gateway.db.session, "commit", lambda: commits.append(pedido.estado))
    monkeypatch.setattr(gateway, "cancelar_stock_confirmado",
                        lambda *a, **k: pytest.fail("no reintegrar un pedido despachado"))

    respuesta = _cliente_admin().post(
        "/pedidos/cambiar-estado/77", data={"estado": "cancelado"},
        headers={"X-Requested-With": "XMLHttpRequest"})

    assert respuesta.status_code == 200
    assert pedido.estado == "cancelado"
    assert commits == ["cancelado"]
