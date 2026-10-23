"""Blueprint proxy del dominio CLIENTES.

Rutas bajo /api/v1/clientes -> microservicio clientes (8004).
- /registro es público (nuevo cliente de la tienda, sin cookie que explotar).
- Un cliente autenticado solo ve/edita SU propio registro; admin y
  vendedor operan sobre cualquier cliente.
"""
import uuid

from flask import Blueprint, g, jsonify, request

from jwt_auth import require_jwt_token, requiere_rol, usuario_actual

from .proxy import proxy_json, url_servicio

bp = Blueprint("api_clientes", __name__, url_prefix="/api/v1/clientes")


def _base():
    return url_servicio("MS_CLIENTES_URL", "http://127.0.0.1:8004")


def _rid():
    return request.headers.get("X-Request-Id") or uuid.uuid4().hex


def _puede_operar(usuario, cid, *roles):
    """True si el rol está permitido O el recurso es del propio usuario."""
    return usuario["rol"] in roles or usuario["id"] == str(cid)


@bp.route("/registro", methods=["POST"])
def registro():
    """Alta de cliente de la tienda (público: no requiere JWT aún)."""
    rid = _rid()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    errores = []
    for campo in ("email", "nombres", "apellidos", "clave",
                  "departamento", "provincia", "distrito"):
        if not str(payload.get(campo) or "").strip():
            errores.append(f"{campo} es requerido")
    if payload.get("email") and "@" not in str(payload["email"]):
        errores.append("correo con formato inválido")
    if payload.get("clave") and len(str(payload["clave"])) < 6:
        errores.append("la clave debe tener al menos 6 caracteres")
    if errores:
        return jsonify({"error": "Datos inválidos", "detalles": errores,
                        "request_id": rid}), 400

    return proxy_json(
        "POST", f"{_base()}/",
        metodo_http=request.method, ruta=request.path,
        payload=payload, headers_origen=dict(request.headers),
        usuario=None, request_id=rid,
        evento="clientes.registro", servicio="clientes",
    )


@bp.route("/listar", methods=["GET"])
@require_jwt_token
@requiere_rol("admin", "vendedor")
def listar():
    return proxy_json(
        "GET", f"{_base()}/",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="clientes.listar", servicio="clientes",
    )


@bp.route("/<int:cid>", methods=["GET"])
@require_jwt_token
def detalle(cid):
    usuario = g.usuario_api
    if not _puede_operar(usuario, cid, "admin", "vendedor"):
        return jsonify({"error": "Solo puede consultar su propio registro",
                        "request_id": _rid()}), 403
    return proxy_json(
        "GET", f"{_base()}/{cid}",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=usuario,
        request_id=_rid(), evento="clientes.detalle", servicio="clientes",
    )


@bp.route("/<int:cid>", methods=["PUT"])
@require_jwt_token
def actualizar(cid):
    usuario = g.usuario_api
    if not _puede_operar(usuario, cid, "admin"):
        return jsonify({"error": "Solo puede editar su propio registro",
                        "request_id": _rid()}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not payload:
        return jsonify({"error": "Debe enviar al menos un campo",
                        "request_id": _rid()}), 400
    # Un cliente no se auto-asigna un estado/rol arbitrario.
    if usuario["rol"] not in ("admin", "vendedor"):
        for restringido in ("estado",):
            payload.pop(restringido, None)
        if not payload:
            return jsonify({"error": "Sin campos permitidos para actualizar",
                            "request_id": _rid()}), 400
    return proxy_json(
        "PUT", f"{_base()}/{cid}",
        metodo_http=request.method, ruta=request.path,
        payload=payload, headers_origen=dict(request.headers),
        usuario=usuario, request_id=_rid(),
        evento="clientes.actualizar", servicio="clientes",
    )


@bp.route("/<int:cid>", methods=["DELETE"])
@require_jwt_token
@requiere_rol("admin")
def eliminar(cid):
    return proxy_json(
        "DELETE", f"{_base()}/{cid}",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="clientes.eliminar", servicio="clientes",
    )


@bp.route("/ubicacion", methods=["GET"])
@require_jwt_token
@requiere_rol("admin")
def ubicacion():
    return proxy_json(
        "GET", f"{_base()}/ubicacion",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="clientes.ubicacion", servicio="clientes",
    )
