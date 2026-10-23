"""Pruebas UNITARIAS de helpers puros del gateway y del monolito.

- api_gateway_setup._en: enrutado CSRF por prefijo de ruta.
- consumidor_copias._entero: casteo defensivo de enteros.
- app._servicio_de_sql: dueno de cada tabla (enrutado multi-bind).
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))

pytestmark = pytest.mark.unitarias


def test_en_detecta_prefijo_v1():
    from api_gateway_setup import _en
    assert _en("/api/v1/ventas", "/api/v1/")
    assert _en("/api/v1/auth/login", "/api/v1/")
    assert not _en("/api/comercial/pedidos", "/api/v1/")
    assert not _en("/productos", "/api/")
    assert not _en(None, "/api/")


def test_entero_convierte_o_devuelve_none():
    from consumidor_copias import _entero
    assert _entero("5") == 5
    assert _entero(3) == 3
    assert _entero("x") is None
    assert _entero(None) is None


def test_servicio_de_sql_enruta_por_tabla():
    # importar el monolito tiene efectos de arranque (prints, sin consultas)
    import app as monolito
    assert monolito._servicio_de_sql(
        "SELECT * FROM inventario_productos WHERE id=1") == "inventario"
    assert monolito._servicio_de_sql(
        "SELECT id, correo FROM usuarios_sistema") == "usuarios"
    assert monolito._servicio_de_sql(
        "SELECT * FROM clientes") == "clientes"
    assert monolito._servicio_de_sql(
        "SELECT * FROM comercial_pedidos") == "ventas"
    # dos duenos en la misma consulta -> ambiguo -> None (usa el motor por defecto)
    assert monolito._servicio_de_sql(
        "SELECT * FROM clientes JOIN productos") is None
    assert monolito._servicio_de_sql("") is None
    assert monolito._servicio_de_sql(None) is None
