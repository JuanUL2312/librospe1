"""Pruebas E2E: flujo completo de venta del POS por HTTP.

Login (JWT) -> catalogo del inventario -> crear venta en el servicio de
ventas -> verificar que la venta figura en el listado. Sin navegador:
usa los procesos vivos (servicios + gateway) tal como en produccion.
La fila de venta creada se elimina al final.
"""
import jwt as pyjwt
import requests

import pytest

pytestmark = pytest.mark.e2e


def test_flujo_completo_venta_pos(gateway, admin_jwt, env_prueba):
    # 1. catalogo (gateway -> inventario)
    r = requests.get(f"{gateway}/api/v1/inventario/productos",
                     headers=admin_jwt, timeout=15)
    assert r.status_code == 200
    productos = r.json()
    assert productos, "el inventario no devolvio productos"
    pid = productos[0]["id"]

    # 2. crear la venta (validacion del gateway + insercion en servicio ventas)
    r = requests.post(f"{gateway}/api/v1/ventas/crear",
                      json={"producto_id": pid, "cantidad": 1},
                      headers=admin_jwt, timeout=15)
    assert r.status_code == 201, r.text[:200]
    cuerpo = r.json()
    assert cuerpo["ok"] is True
    venta_id = cuerpo["id"]

    try:
        # 3. la venta aparece en el listado (gateway -> servicio ventas)
        r = requests.get(f"{gateway}/api/v1/ventas/listar",
                         headers=admin_jwt, timeout=20)
        assert r.status_code == 200
        ids = [v.get("id") for v in r.json()]
        assert venta_id in ids

        # 4. el inventario sigue sano tras la venta
        r = requests.get(f"{gateway}/api/v1/inventario/productos",
                         headers=admin_jwt, timeout=15)
        assert r.status_code == 200
    finally:
        from conftest import borrar_fila
        borrar_fila(env_prueba.get("MS_VENTAS_DB", "librospe_ms_ventas"),
                    "comercial_ventas", "id", venta_id, env_prueba)


def test_rol_cliente_no_puede_vender(gateway, env_prueba):
    """Autorizacion por rol del flujo critico: JWT de cliente -> 403."""
    token = pyjwt.encode(
        {"sub": "99", "rol": "cliente", "iat": 1, "exp": 4102444800,
         "typ": "access"},
        env_prueba["SECRET_KEY"], algorithm="HS256")
    r = requests.post(f"{gateway}/api/v1/ventas/crear",
                      json={"producto_id": 1},
                      headers={"Authorization": "Bearer " + token},
                      timeout=10)
    assert r.status_code == 403
