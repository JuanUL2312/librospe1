"""Blueprint proxy del dominio VENTAS.

Flujo de POST /api/v1/ventas/crear:
  cliente (JWT) -> gateway: valida JWT, audita, inyecta identidad ->
  HTTP + X-Service-Token -> microservicio ventas (MS_VENTAS_URL, 8002).
"""
import uuid

from flask import Blueprint, g, jsonify, request

from jwt_auth import require_jwt_token, requiere_rol

from .proxy import proxy_json, url_servicio

bp = Blueprint("api_ventas", __name__, url_prefix="/api/v1/ventas")


def _base():
    return url_servicio("MS_VENTAS_URL", "http://127.0.0.1:8002")


def _request_id():
    return request.headers.get("X-Request-Id") or uuid.uuid4().hex


@bp.route("/crear", methods=["POST"])
@require_jwt_token
@requiere_rol("admin", "vendedor")
def crear_venta():
    """Registra una venta delegando en el microservicio de ventas (solo personal)."""
    usuario = g.usuario_api
    rid = _request_id()
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        payload = {}
        return jsonify({"error": "El cuerpo debe ser JSON", "request_id": rid}), 400

    # Validaciones de entrada (fallan ANTES de contactar el microservicio).
    errores = []
    if not payload.get("producto_id"):
        errores.append("producto_id es requerido")
    else:
        try:
            payload["producto_id"] = int(payload["producto_id"])
        except (TypeError, ValueError):
            errores.append("producto_id debe ser numérico")
    cantidad = payload.get("cantidad", 1)
    try:
        cantidad = int(cantidad)
        if cantidad < 1:
            errores.append("cantidad debe ser mayor que cero")
        payload["cantidad"] = cantidad
    except (TypeError, ValueError):
        errores.append("cantidad debe ser un entero")
    if errores:
        return jsonify({"error": "Datos inválidos", "detalles": errores,
                        "request_id": rid}), 400

    # La identidad SIEMPRE viene del token: el cliente no puede vender "por otro".
    payload["vendedor_id"] = int(usuario["id"])

    return proxy_json(
        "POST", f"{_base()}/ventas",
        metodo_http=request.method, ruta=request.path,
        payload=payload, headers_origen=dict(request.headers),
        usuario=usuario, request_id=rid,
        evento="ventas.crear", servicio="ventas",
    )


@bp.route("/listar", methods=["GET"])
@require_jwt_token
@requiere_rol("admin", "vendedor")
def listar_ventas():
    """Consulta las ventas del microservicio (solo admin/vendedor)."""
    return proxy_json(
        "GET", f"{_base()}/ventas",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers),
        usuario=g.usuario_api, request_id=_request_id(),
        evento="ventas.listar", servicio="ventas",
    )
