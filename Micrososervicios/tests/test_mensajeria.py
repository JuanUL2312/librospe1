"""Pruebas del agente de mensajes (RabbitMQ) con un pika simulado.

Verifica la publicacion (exchange topic, routing key, payload, confirmacion),
el consumo (handler + ack) y el respaldo al outbox cuando no hay broker.
"""
import json
import os
import sys
import types
import pathlib

import pytest

WWW = pathlib.Path(__file__).resolve().parent.parent / "www"
sys.path.insert(0, str(WWW))

publicados = []
declarados = {"exchanges": [], "queues": [], "bindings": [], "acks": [], "nacks": []}


class FakeProps:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeCanal:
    def __init__(self):
        self._entrega = None

    def exchange_declare(self, exchange=None, exchange_type=None, durable=None):
        declarados.setdefault("exchanges", []).append((exchange, exchange_type, durable))

    def queue_declare(self, queue=None, durable=None):
        declarados.setdefault("queues", []).append((queue, durable))

    def queue_bind(self, exchange=None, queue=None, routing_key=None):
        declarados.setdefault("bindings", []).append((exchange, queue, routing_key))

    def confirm_delivery(self):
        declarados.setdefault("confirms", []).append(True)

    def basic_publish(self, exchange=None, routing_key=None, body=None, properties=None):
        publicados.append({"exchange": exchange, "routing_key": routing_key,
                           "body": json.loads(body.decode("utf-8")), "props": properties})

    def basic_get(self, queue=None, auto_ack=False):
        if not self._entrega:
            return None, None, None
        entrega, self._entrega = self._entrega, None
        return entrega

    def basic_ack(self, tag):
        declarados.setdefault("acks", []).append(tag)

    def basic_nack(self, tag, requeue=True):
        declarados.setdefault("nacks", []).append((tag, requeue))


class FakeConexion:
    def __init__(self, *a, **k):
        self.canal = FakeCanal()
        self.cerrada = False

    def channel(self):
        return self.canal

    def close(self):
        self.cerrada = True


class FakeEntrega:
    def __init__(self, cuerpo):
        self.delivery_tag = 42
        self.cuerpo = cuerpo


class FakeParams:
    def __init__(self, url):
        self.url = url
        self.heartbeat = None
        self.blocked_connection_timeout = None
        self.connection_attempts = None
        self.retry_delay = None


@pytest.fixture()
def mensajeria(monkeypatch):
    """Modulo de mensajeria con pika simulado."""
    pika_fake = types.ModuleType("pika")
    pika_fake.URLParameters = FakeParams
    pika_fake.BlockingConnection = FakeConexion
    pika_fake.BasicProperties = FakeProps
    monkeypatch.setitem(sys.modules, "pika", pika_fake)
    publicados.clear()
    declarados.clear()
    import importlib
    import mensajeria as M
    importlib.reload(M)
    return M


def test_configuracion(mensajeria):
    assert mensajeria.EXCHANGE == "librospe.eventos"
    assert set(mensajeria.COLAS) == {"inventario", "ventas", "usuarios", "clientes"}
    assert len(mensajeria.EVENTOS) >= 8
    assert "inventario" in mensajeria.EVENTOS["pedido.creado"]
    assert "ventas" in mensajeria.EVENTOS["pedido.creado"]


def test_publicacion(mensajeria, monkeypatch):
    monkeypatch.setenv("AMQP_URL", "amqp://guest:guest@localhost:5672//")
    ok, detalle = mensajeria._publicar_en_broker("pedido.creado", {"pedido_id": 7}, "gateway")
    assert ok, detalle
    assert ("librospe.eventos", "topic", True) in declarados["exchanges"]
    assert len(publicados) == 1
    ev = publicados[0]
    assert ev["routing_key"] == "pedido.creado"
    assert ev["exchange"] == "librospe.eventos"
    assert ev["body"]["tipo"] == "pedido.creado"
    assert ev["body"]["origen"] == "gateway"
    assert ev["body"]["datos"]["pedido_id"] == 7
    assert ev["props"].delivery_mode == 2      # persistente
    assert declarados.get("confirms")


def test_consumo(mensajeria, monkeypatch):
    recibidos = []

    def handler(tipo, datos):
        recibidos.append((tipo, datos))
        return True

    cuerpo = json.dumps({"tipo": "pedido.creado", "origen": "gateway",
                          "datos": {"pedido_id": 9}}).encode("utf-8")
    conexion = FakeConexion()
    conexion.canal._entrega = (FakeEntrega(cuerpo), FakeProps(type="pedido.creado"), cuerpo)
    monkeypatch.setattr(mensajeria, "_conexion", lambda *a, **k: (conexion, ""))

    cola = mensajeria._declarar_canal(FakeParams("x"), conexion.canal, "inventario")
    assert cola == "librospe.inventario"
    assert ("librospe.eventos", "librospe.inventario", "pedido.creado") in declarados["bindings"]

    import threading
    parar = threading.Event()
    parar.set()
    mensajeria.consumir_eventos("inventario", handler, mientras=False)
    assert len(recibidos) == 1
    assert recibidos[0][0] == "pedido.creado"
    assert declarados["acks"] == [42]


def test_respaldo_sin_broker(mensajeria, monkeypatch):
    """Sin broker, el evento va al outbox (no se pierde)."""
    guardados = []
    monkeypatch.delenv("AMQP_URL", raising=False)
    monkeypatch.setattr(mensajeria, "_conexion",
                        lambda *a, **k: (None, "AMQP_URL no configurado"))
    monkeypatch.setattr(mensajeria, "guardar_en_outbox",
                        lambda tipo, datos, origen="gateway": guardados.append((tipo, datos)) or True)
    ok, detalle = mensajeria.publicar_evento("venta.registrada", {"producto_id": 3}, "gateway")
    assert ok is False
    assert "AMQP_URL" in str(detalle)
    assert len(guardados) == 1


def test_texto_del_sms():
    """El texto del SMS debe traer los datos del comprobante."""
    from sms_service import componer_texto
    texto = componer_texto("Boleta de venta", "B001-000123",
                           "JUAN VICTOR UCHUYPOMA", 25.5,
                           "https://librospe.alwaysdata.net/mis-pedidos")
    assert "Boleta de venta" in texto
    assert "B001-000123" in texto
    assert "S/ 25.50" in texto
    assert "mis-pedidos" in texto
    assert len(texto) < 320      # cabe en un SMS
