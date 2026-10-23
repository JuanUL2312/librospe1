"""Pruebas de las consultas dirigidas del consumidor de copias del gateway.

Cada evento solo debe refrescar las tablas que toca (y no el SQL completo de
sincronizar_copias.sql en cada evento); lo que no se puede resolver de forma
dirigida cae en la sincronizacion completa.
"""
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
WWW = RAIZ / "www"
sys.path.insert(0, str(WWW))

import consumidor_copias as C  # noqa: E402


@pytest.fixture(autouse=True)
def limpio():
    C._vistos.clear()
    C._hay_pendientes.clear()
    yield
    C._vistos.clear()
    C._hay_pendientes.clear()


def test_producto_actualizado():
    sents = C._sentencias_dirigidas("producto.actualizado",
                                    {"id": 5, "nombre": "Libro", "cantidad": 3})
    assert sents is not None and len(sents) == 2
    insert, update = sents
    assert "INSERT IGNORE INTO `librospe_ms_ventas`.`productos`" in insert[0]
    assert "FROM `librospe_ms_inventario`.`productos`" in insert[0]
    assert insert[1] == {"pid": 5}
    assert "UPDATE `librospe_ms_ventas`.`productos` d" in update[0]
    assert "s.`id` = :pid" in update[0]
    assert update[1] == {"pid": 5}


def test_alerta_stock_tambien_refresca_el_producto():
    sents = C._sentencias_dirigidas("producto.alerta_stock", {"id": 9, "cantidad": 1})
    assert sents is not None and len(sents) == 2
    assert all("productos" in sql for sql, _ in sents)


def test_venta_registrada_toca_la_venta_y_el_stock():
    sents = C._sentencias_dirigidas("venta.registrada",
                                    {"venta_id": 77, "producto_id": 5, "cantidad": 2})
    assert sents is not None and len(sents) == 4
    # la fila de la venta: ventas -> inventario
    assert "INSERT IGNORE INTO `librospe_ms_inventario`.`ventas`" in sents[0][0]
    assert sents[0][1] == {"vid": 77}
    # el stock cambio en inventario: refrescar la copia del producto en ventas
    assert "INSERT IGNORE INTO `librospe_ms_ventas`.`productos`" in sents[2][0]
    assert sents[2][1] == {"pid": 5}


def test_venta_registrada_sin_producto_no_falla():
    sents = C._sentencias_dirigidas("venta.registrada", {"venta_id": 77})
    assert sents is not None and len(sents) == 2


def test_cliente_registrado_por_correo():
    sents = C._sentencias_dirigidas("cliente.registrado", {"email": "ana@x.com",
                                                           "nombres": "Ana"})
    assert sents is not None and len(sents) == 2
    assert "INSERT IGNORE INTO `librospe_ms_ventas`.`clientes`" in sents[0][0]
    assert "`correo` = :correo" in sents[0][0]
    assert sents[0][1] == {"correo": "ana@x.com"}


def test_pedido_creado_copia_sus_ventas_y_sus_productos():
    sents = C._sentencias_dirigidas("pedido.creado", {
        "pedido_id": 12,
        "items": [{"id": 3, "cantidad": 1}, {"id": 5, "cantidad": 2}, {"id": "x"}],
    })
    assert sents is not None and len(sents) == 4
    assert "INSERT IGNORE INTO `librospe_ms_inventario`.`ventas`" in sents[0][0]
    assert "`pedido_id` = :pedido" in sents[0][0]
    assert sents[0][1] == {"pedido": 12}
    assert "`id` IN (:p0, :p1)" in sents[2][0]
    assert sents[2][1] == {"p0": 3, "p1": 5}


def test_eventos_no_resolubles_dan_none():
    assert C._sentencias_dirigidas("servicio.ping", {"cualquier": 1}) is None
    assert C._sentencias_dirigidas("producto.actualizado", {"nombre": "sin id"}) is None
    assert C._sentencias_dirigidas("cliente.registrado", {"nombres": "sin correo"}) is None
    assert C._sentencias_dirigidas("pedido.creado", {"items": []}) is None
    assert C._sentencias_dirigidas("pedido.creado", {"pedido_id": "x", "items": []}) is None
    assert C._sentencias_dirigidas("pedido.creado", None) is None


def test_columnas_igual_que_el_script_de_sincronizacion():
    """Si sincronizar_copias.sql cambia de columnas, este test avisa."""
    sql = (RAIZ / "sincronizar_copias.sql").read_text(encoding="utf-8")

    def columnas_script(destino, tabla):
        m = re.search(rf"INSERT IGNORE INTO `{destino}`.`{tabla}` \(([^)]*)\)", sql)
        assert m, f"no esta la copia {destino}.{tabla} en sincronizar_copias.sql"
        return tuple(c.strip().strip("`") for c in m.group(1).split(","))

    assert C.COLUMNAS_PRODUCTOS == columnas_script("librospe_ms_ventas", "productos")
    assert C.COLUMNAS_VENTAS == columnas_script("librospe_ms_inventario", "ventas")
    assert C.COLUMNAS_CLIENTES == columnas_script("librospe_ms_ventas", "clientes")


def test_dedupe_del_mismo_evento(monkeypatch):
    assert C._recien_visto("venta.registrada:77") is False
    assert C._recien_visto("venta.registrada:77") is True
    assert C._recien_visto("venta.registrada:78") is False
    # fuera de la ventana vuelve a contarse
    monkeypatch.setattr(C, "VENTANA_DEDUP", 0.0)
    assert C._recien_visto("venta.registrada:77") is False


def test_handler_sin_resolver_pide_sincronizacion_completa():
    assert C._handler("servicio.ping", {}) is True
    assert C._hay_pendientes.is_set()
    C._hay_pendientes.clear()
    # payload ilegible: no lanza, cae en la sincronizacion completa
    assert C._handler("producto.actualizado", None) is True
    assert C._hay_pendientes.is_set()


def test_handler_duplicado_no_vuelve_a_resolver(monkeypatch):
    llamadas = []
    monkeypatch.setattr(C, "_sentencias_dirigidas",
                        lambda tipo, datos: llamadas.append(tipo))
    assert C._handler("producto.actualizado", {"id": 1}) is True
    assert C._handler("producto.actualizado", {"id": 1}) is True
    assert llamadas == ["producto.actualizado"]   # la segunda vez se ignora
    assert C._hay_pendientes.is_set()
