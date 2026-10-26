"""Regresiones unitarias para el descuento condicional de inventario."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "www"))

import app as gateway  # noqa: E402
import stock  # noqa: E402


class QueryFalsa:
    def __init__(self):
        self.condiciones = None
        self.actualizacion = None
        self.resultado = 1

    def filter(self, *condiciones):
        self.condiciones = condiciones
        return self

    def update(self, valores, synchronize_session=False):
        self.actualizacion = valores
        return self.resultado


def test_descuento_stock_condicionado_a_disponibilidad(monkeypatch):
    query = QueryFalsa()
    monkeypatch.setattr(gateway.db.session, "query", lambda modelo: query)
    assert gateway._descontar_stock_atomico(12, 3) is True
    assert len(query.condiciones) == 2
    assert "productos.id" in str(query.condiciones[0])
    assert "productos.cantidad" in str(query.condiciones[1])
    assert query.actualizacion[gateway.Producto.cantidad] is not None


def test_descuento_stock_rechazado_si_update_no_afecta_filas(monkeypatch):
    query = QueryFalsa()
    query.resultado = 0
    monkeypatch.setattr(gateway.db.session, "query", lambda modelo: query)
    assert gateway._descontar_stock_atomico(12, 4) is False


def test_reserva_falla_cerrado_si_inventario_no_responde(monkeypatch):
    monkeypatch.setattr(stock, "_post",
                        lambda *args, **kwargs: (None, {"error": "timeout"}))
    monkeypatch.setattr(stock, "_reservar_directo",
                        lambda *args, **kwargs: (_ for _ in ()).throw(
                            AssertionError("el gateway no debe escribir la BD")))
    with gateway.app.app_context():
        gateway.app.config["INVENTARIO_DB_FALLBACK"] = False
        resultado = stock.reservar_stock(
            "failclosed-123456", [{"id": 1, "cantidad": 1}])
    assert resultado["ok"] is False
    assert resultado["codigo"] == "inventario_no_disponible"


def test_peticion_http_de_reserva_envia_token_interno(monkeypatch):
    class Respuesta:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"ok": true}'

    capturada = {}
    monkeypatch.setattr(stock, "_url_inventario", lambda: "http://inventario:8001")
    monkeypatch.setattr(stock, "_token_servicio", lambda: "token-de-prueba")
    def abrir(request, timeout):
        capturada["request"] = request
        return Respuesta()
    monkeypatch.setattr(stock, "urlopen", abrir)
    status, cuerpo = stock._post("/_reservar-stock", {"referencia": "token-test-123"})
    assert status == 200 and cuerpo["ok"] is True
    assert capturada["request"].get_header("X-service-token") == "token-de-prueba"


def test_cancelacion_usa_fallback_si_servicio_aun_no_tiene_la_ruta(monkeypatch):
    llamada = {}
    monkeypatch.setattr(stock, "_post",
                        lambda *args, **kwargs: (404, {"error": "Not Found"}))
    def devolver(referencia, documento_id, documento_tipo):
        llamada.update(referencia=referencia, documento_id=documento_id,
                       documento_tipo=documento_tipo)
        return {"ok": True, "via": "bd"}
    monkeypatch.setattr(stock, "_cancelar_stock_directo", devolver)
    with gateway.app.app_context():
        gateway.app.config["INVENTARIO_DB_FALLBACK"] = True
        resultado = stock.cancelar_stock_confirmado(
            "cancel-key-123", 42, documento_tipo="pedido")
    assert resultado == {"ok": True, "via": "bd"}
    assert llamada == {"referencia": "cancel-key-123", "documento_id": 42,
                       "documento_tipo": "pedido"}
