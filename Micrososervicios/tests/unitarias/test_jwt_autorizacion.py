"""Pruebas UNITARIAS: JWT (emision, validacion y autorizacion por rol).

Usa una mini-app Flask con SECRET_KEY propia: sin base de datos y sin red.
El manejo de `TokenInvalido` replica el del gateway (JSON + codigo).
"""
import pytest
from flask import Flask

import jwt as pyjwt

import jwt_auth

pytestmark = pytest.mark.unitarias


CLAVE_PRUEBA = "secreto-de-prueba-de-al-menos-32-bytes"


@pytest.fixture
def app_jwt():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = CLAVE_PRUEBA
    app.config["JWT_MINUTOS"] = 60

    @app.errorhandler(jwt_auth.TokenInvalido)
    def _token_invalido(e):
        return {"error": e.detalle}, e.codigo

    @app.route("/protegida")
    @jwt_auth.require_jwt_token
    @jwt_auth.requiere_rol("admin")
    def protegida():
        return {"hola": jwt_auth.usuario_actual()["id"]}, 200

    return app


def test_token_roundtrip_con_claims(app_jwt):
    with app_jwt.app_context():
        token, segundos = jwt_auth.crear_token(
            7, "admin", correo="a@b.c", nombre="Ana")
        assert segundos > 0
        p = jwt_auth.decodificar_token(token)
        assert p["sub"] == "7"
        assert p["rol"] == "admin"
        assert p["correo"] == "a@b.c"
        assert p["typ"] == "access"
        assert p["jti"]


def test_token_expirado_se_rechaza(app_jwt):
    with app_jwt.app_context():
        token, _ = jwt_auth.crear_token(1, "admin", minutos=-1)
        with pytest.raises(jwt_auth.TokenInvalido, match="expirado"):
            jwt_auth.decodificar_token(token)


def test_firma_con_otra_clave_se_rechaza(app_jwt):
    with app_jwt.app_context():
        token, _ = jwt_auth.crear_token(1, "admin")
    otro = Flask(__name__)
    otro.config["SECRET_KEY"] = "clave-diferente"
    with otro.app_context():
        with pytest.raises(jwt_auth.TokenInvalido, match="inválido"):
            jwt_auth.decodificar_token(token)


def test_typ_distinto_de_access_se_rechaza(app_jwt):
    with app_jwt.app_context():
        payload = {
            "sub": "1", "rol": "admin", "iat": 1, "exp": 9999999999,
            "typ": "refresh",
        }
        token = pyjwt.encode(payload, CLAVE_PRUEBA, algorithm="HS256")
        with pytest.raises(jwt_auth.TokenInvalido, match="Tipo de token"):
            jwt_auth.decodificar_token(token)


def test_extraer_bearer(app_jwt):
    with app_jwt.test_request_context(headers={}):
        with pytest.raises(jwt_auth.TokenInvalido, match="Authorization"):
            jwt_auth.extraer_bearer()
    with app_jwt.test_request_context(headers={"Authorization": "Token x"}):
        with pytest.raises(jwt_auth.TokenInvalido, match="Bearer"):
            jwt_auth.extraer_bearer()
    with app_jwt.test_request_context(headers={"Authorization": "Bearer "}):
        with pytest.raises(jwt_auth.TokenInvalido, match="vacío"):
            jwt_auth.extraer_bearer()
    with app_jwt.test_request_context(headers={"Authorization": "Bearer abc.def.ghi"}):
        assert jwt_auth.extraer_bearer() == "abc.def.ghi"


def test_ruta_sin_token_da_401(app_jwt):
    r = app_jwt.test_client().get("/protegida")
    assert r.status_code == 401
    assert "Bearer" in r.get_json()["error"]


def test_ruta_con_token_admin_pasa(app_jwt):
    with app_jwt.app_context():
        token, _ = jwt_auth.crear_token(7, "admin")
    r = app_jwt.test_client().get(
        "/protegida", headers={"Authorization": "Bearer " + token})
    assert r.status_code == 200
    assert r.get_json() == {"hola": "7"}


def test_ruta_con_rol_no_autorizado_da_403(app_jwt):
    with app_jwt.app_context():
        token, _ = jwt_auth.crear_token(9, "vendedor")
    r = app_jwt.test_client().get(
        "/protegida", headers={"Authorization": "Bearer " + token})
    assert r.status_code == 403
    cuerpo = r.get_json()
    assert cuerpo["rol_requerido"] == ["admin"]
    assert cuerpo["rol_actual"] == "vendedor"
