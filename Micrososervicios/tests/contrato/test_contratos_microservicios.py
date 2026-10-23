"""Pruebas de CONTRATO: la forma del JSON que publican los microservicios.

Congelan el "idioma" proveedor-consumidor: si un servicio cambia claves o
tipos, estas pruebas fallan ANTES de llegar a Alwaysdata. No escriben en la
BD; solo leen y verifican estructura.
"""
import requests

import pytest

pytestmark = pytest.mark.contrato

BASE = {
    "inventario": "http://127.0.0.1:8001",
    "ventas": "http://127.0.0.1:8002",
    "usuarios": "http://127.0.0.1:8003",
    "clientes": "http://127.0.0.1:8004",
}


# ------------------------------- inventario -------------------------------

def test_inventario_health(servicios):
    d = requests.get(f"{BASE['inventario']}/health", timeout=10).json()
    assert d["status"] == "OK"
    assert d["servicio"] == "inventario"
    assert isinstance(d["productos"], int)


def test_inventario_lista_productos_con_keys_estables(servicios):
    r = requests.get(f"{BASE['inventario']}/productos", timeout=10)
    assert r.status_code == 200
    datos = r.json()
    assert isinstance(datos, list) and datos
    for p in datos[:5]:
        assert {"id", "nombre", "precio"} <= set(p)


def test_inventario_detalle_inexistente_devuelve_error(servicios):
    r = requests.get(f"{BASE['inventario']}/productos/999999", timeout=10)
    assert r.status_code == 404
    assert r.json() == {"error": "No encontrado"}


def test_inventario_verificar_stock_requiere_token(servicios, env_prueba):
    url = f"{BASE['inventario']}/_verificar-stock/1/1"
    r = requests.get(url, timeout=10)
    assert r.status_code == 401
    assert r.json()["error"] == "Token de servicio invalido"
    r = requests.get(url, headers={
        "X-Service-Token": env_prueba.get("SERVICE_TOKEN", "")}, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["producto_id"] == 1
    assert isinstance(d["disponible"], bool)
    assert isinstance(d["stock_actual"], int)


# -------------------------------- usuarios --------------------------------

def test_usuarios_health(servicios):
    d = requests.get(f"{BASE['usuarios']}/health", timeout=10).json()
    assert d["status"] == "OK"
    assert d["servicio"] == "usuarios"
    assert isinstance(d["usuarios"], int)


def test_usuarios_lista_con_keys_estables(servicios):
    r = requests.get(f"{BASE['usuarios']}/", timeout=10)
    assert r.status_code == 200
    datos = r.json()
    assert isinstance(datos, list) and datos
    for u in datos[:5]:
        assert {"id", "correo", "rol"} <= set(u)


def test_usuarios_roles_es_lista(servicios):
    r = requests.get(f"{BASE['usuarios']}/roles", timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_usuarios_escritura_sin_token_da_401(servicios):
    r = requests.post(f"{BASE['usuarios']}/", json={}, timeout=10)
    assert r.status_code == 401
    assert r.json() == {"error": "Token invalido"}


# -------------------------------- clientes --------------------------------

def test_clientes_health(servicios):
    d = requests.get(f"{BASE['clientes']}/health", timeout=10).json()
    assert d["status"] == "OK"
    assert d["servicio"] == "clientes"


def test_clientes_lista(servicios):
    r = requests.get(f"{BASE['clientes']}/", timeout=10)
    assert r.status_code == 200
    datos = r.json()
    assert isinstance(datos, list)
    if datos:
        assert "id" in datos[0]


def test_clientes_ubicacion_responde_json(servicios):
    r = requests.get(f"{BASE['clientes']}/ubicacion", timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


# --------------------------------- ventas ---------------------------------

def test_ventas_health(servicios):
    d = requests.get(f"{BASE['ventas']}/health", timeout=10).json()
    assert d["status"] == "OK"
    assert d["servicio"] == "ventas"
    assert isinstance(d["pedidos"], int)


def test_ventas_lista_y_pedidos(servicios):
    r = requests.get(f"{BASE['ventas']}/ventas", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = requests.get(f"{BASE['ventas']}/pedidos", timeout=15)
    assert r.status_code == 200
    pedidos = r.json()
    assert isinstance(pedidos, list)
    if pedidos:
        assert {"id", "cliente_id"} <= set(pedidos[0])


def test_ventas_validar_stock_delega_en_inventario(servicios):
    r = requests.get(f"{BASE['ventas']}/validar-stock/1/1", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["origen"] == "ventas"
    assert "respuesta" in d
    assert isinstance(d["respuesta"]["disponible"], bool)
