"""Blueprint proxy del dominio USUARIOS (gestión del sistema).

Rutas bajo /api/v1/usuarios -> microservicio usuarios (8003).
Solo admin gestiona usuarios; vendedor puede consultar roles.
"""
import uuid

from flask import Blueprint, g, jsonify, request

from jwt_auth import require_jwt_token, requiere_rol

from .proxy import proxy_json, url_servicio

bp = Blueprint("api_usuarios", __name__, url_prefix="/api/v1/usuarios")


def _base():
    return url_servicio("MS_USUARIOS_URL", "http://127.0.0.1:8003")


def _rid():
    return request.headers.get("X-Request-Id") or uuid.uuid4().hex


@bp.route("/listar", methods=["GET"])
@require_jwt_token
@requiere_rol("admin")
def listar():
    return proxy_json(
        "GET", f"{_base()}/",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="usuarios.listar", servicio="usuarios",
    )


@bp.route("/roles", methods=["GET"])
@require_jwt_token
@requiere_rol("admin", "vendedor")
def roles():
    return proxy_json(
        "GET", f"{_base()}/roles",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="usuarios.roles", servicio="usuarios",
    )


@bp.route("/crear", methods=["POST"])
@require_jwt_token
@requiere_rol("admin")
def crear():
    usuario = g.usuario_api
    rid = _rid()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    errores = []
    for campo in ("correo", "nombres", "apellidos"):
        if not str(payload.get(campo) or "").strip():
            errores.append(f"{campo} es requerido")
    if payload.get("correo") and "@" not in str(payload["correo"]):
        errores.append("correo con formato inválido")
    if not payload.get("clave"):
        errores.append("clave es requerida")
    if errores:
        return jsonify({"error": "Datos inválidos", "detalles": errores,
                        "request_id": rid}), 400

    return proxy_json(
        "POST", f"{_base()}/",
        metodo_http=request.method, ruta=request.path,
        payload=payload, headers_origen=dict(request.headers),
        usuario=usuario, request_id=rid,
        evento="usuarios.crear", servicio="usuarios",
    )


@bp.route("/<int:uid>", methods=["PUT"])
@require_jwt_token
@requiere_rol("admin")
def actualizar(uid):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not payload:
        return jsonify({"error": "Debe enviar al menos un campo",
                        "request_id": _rid()}), 400
    return proxy_json(
        "PUT", f"{_base()}/{uid}",
        metodo_http=request.method, ruta=request.path,
        payload=payload, headers_origen=dict(request.headers),
        usuario=g.usuario_api, request_id=_rid(),
        evento="usuarios.actualizar", servicio="usuarios",
    )


@bp.route("/<int:uid>", methods=["DELETE"])
@require_jwt_token
@requiere_rol("admin")
def eliminar(uid):
    """Borrado lógico (estado=0) en el microservicio de usuarios."""
    return proxy_json(
        "DELETE", f"{_base()}/{uid}",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="usuarios.eliminar", servicio="usuarios",
    )
