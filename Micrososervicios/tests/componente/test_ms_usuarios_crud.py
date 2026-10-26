"""Pruebas de COMPONENTE: el microservicio de USUARIOS aislando la red.

Usa el cliente de pruebas nativo de Flask contra la app del servicio
(sin gateway, sin RabbitMQ), con su BD real y filas de prueba que se
eliminan al final.
"""
import importlib.util
import sys
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.componente


def _app_usuarios():
    ruta = RAIZ / "servicio-usuarios" / "app.py"
    spec = importlib.util.spec_from_file_location("ms_usuarios_componente", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app


def test_crud_usuario_aislado(env_prueba):
    app = _app_usuarios()
    cliente = app.test_client()
    token = {"X-Service-Token": env_prueba.get("SERVICE_TOKEN", "")}
    correo = f"comp-{uuid.uuid4().hex[:10]}@librospe.test"

    # escritura sin token -> 401 (contrato de seguridad)
    r = cliente.post("/", json={"correo": correo})
    assert r.status_code == 401

    # creacion
    r = cliente.post("/", json={
        "correo": correo, "nombres": "Componente", "apellidos": "Prueba",
        "clave": "Comp#2026", "rol": "vendedor",
    }, headers=token)
    assert r.status_code == 201, r.get_json()
    uid = r.get_json()["id"]
    try:
        # lectura: aparece en la lista
        assert cliente.get("/").status_code == 401
        lista = cliente.get("/", headers=token).get_json()
        assert any(u.get("correo") == correo for u in lista)

        # actualizacion
        r = cliente.put(f"/{uid}", json={"nombres": "Modificado"},
                        headers=token)
        assert r.status_code == 200
        assert cliente.get(f"/{uid}").status_code == 401
        det = cliente.get(f"/{uid}", headers=token).get_json()
        assert det["nombres"] == "Modificado"

        # baja logica (DELETE pone estado=0, no borra la fila)
        r = cliente.delete(f"/{uid}", headers=token)
        assert r.status_code == 200
        assert cliente.get(f"/{uid}", headers=token).get_json()["estado"] == 0
    finally:
        # limpieza REAL de la fila de prueba
        from conftest import borrar_fila
        borrar_fila(env_prueba.get("MS_USUARIOS_DB", "librospe_ms_usuarios"),
                    "usuarios_sistema", "id", uid, env_prueba)


def test_login_interno_valida_credenciales(env_prueba):
    app = _app_usuarios()
    cliente = app.test_client()
    token = {"X-Service-Token": env_prueba.get("SERVICE_TOKEN", "")}
    r = cliente.post("/validar-credenciales",
                     json={"correo": "nadie@librospe.test", "clave": "x"},
                     headers=token)
    assert r.status_code == 401
    assert r.get_json()["error"] == "Credenciales invalidas"
