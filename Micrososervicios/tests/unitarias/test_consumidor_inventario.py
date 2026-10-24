"""El consumidor de inventario NO descuenta stock al recibir eventos.

El descuento ocurre una sola vez en la reserva atomica del checkout. Los
eventos `pedido.creado` y `venta.registrada` son informativos: si se repiten
(o RabbitMQ los reentrega) no pueden producir un segundo descuento.
"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def inventario():
    sys.modules.setdefault("pytest", sys.modules.get("pytest"))
    ruta = RAIZ / "servicio-inventario" / "app.py"
    spec = importlib.util.spec_from_file_location(
        "ms_inventario_consumidor", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _SesionProhibida:
    """Falla si el handler intenta tocar la base de datos."""

    def __getattr__(self, nombre):
        raise AssertionError(
            f"el evento informativo no debe acceder a la BD (.{nombre})")


def test_pedido_creado_y_venta_registrada_son_informativos(inventario,
                                                            monkeypatch):
    monkeypatch.setattr(inventario, "db",
                        SimpleNamespace(session=_SesionProhibida()))
    datos = {"pedido_id": 1, "items": [{"id": 2, "cantidad": 3}]}

    assert inventario._aplicar_evento("pedido.creado", datos) is True
    assert inventario._aplicar_evento("pedido.creado", datos) is True
    assert inventario._aplicar_evento("venta.registrada", datos) is True
    assert inventario._aplicar_evento("venta.registrada", datos) is True


def test_evento_desconocido_no_se_reencola(inventario, monkeypatch):
    monkeypatch.setattr(inventario, "db",
                        SimpleNamespace(session=_SesionProhibida()))
    assert inventario._aplicar_evento("otro.servicio", {}) is True
