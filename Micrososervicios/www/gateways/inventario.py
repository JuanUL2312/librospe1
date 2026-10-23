"""Blueprint proxy del dominio INVENTARIO.

Rutas bajo /api/v1/inventario -> microservicio inventario (8001).
Nota de seguridad: el microservicio deja PUT /stock/<id> SIN su
X-Service-Token; en el gateway esa escritura queda cubierta por JWT +
rol exigido.
"""
import uuid

from flask import Blueprint, g, jsonify, request

from jwt_auth import require_jwt_token, requiere_rol

from .proxy import proxy_json, url_servicio

bp = Blueprint("api_inventario", __name__, url_prefix="/api/v1/inventario")


def _base():
    return url_servicio("MS_INVENTARIO_URL", "http://127.0.0.1:8001")


def _rid():
    return request.headers.get("X-Request-Id") or uuid.uuid4().hex


@bp.route("/productos", methods=["GET"])
@require_jwt_token
def listar_productos():
    return proxy_json(
        "GET", f"{_base()}/productos",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="inventario.productos.listar",
        servicio="inventario",
    )


@bp.route("/productos/<int:pid>", methods=["GET"])
@require_jwt_token
def detalle_producto(pid):
    return proxy_json(
        "GET", f"{_base()}/productos/{pid}",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="inventario.producto.detalle",
        servicio="inventario",
    )


@bp.route("/productos", methods=["POST"])
@require_jwt_token
@requiere_rol("admin")
def crear_producto():
    usuario = g.usuario_api
    rid = _rid()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    errores = []
    if not str(payload.get("nombre") or "").strip():
        errores.append("nombre es requerido")
    for campo in ("cantidad", "precio"):
        if payload.get(campo) is None:
            errores.append(f"{campo} es requerido")
        else:
            try:
                payload[campo] = (int(payload[campo]) if campo == "cantidad"
                                  else float(payload[campo]))
                if campo == "cantidad" and payload[campo] < 0:
                    errores.append("cantidad no puede ser negativa")
            except (TypeError, ValueError):
                errores.append(f"{campo} debe ser numérico")
    if errores:
        return jsonify({"error": "Datos inválidos", "detalles": errores,
                        "request_id": rid}), 400

    return proxy_json(
        "POST", f"{_base()}/productos",
        metodo_http=request.method, ruta=request.path,
        payload=payload, headers_origen=dict(request.headers),
        usuario=usuario, request_id=rid,
        evento="inventario.producto.crear", servicio="inventario",
    )


@bp.route("/productos/<int:pid>", methods=["PUT"])
@require_jwt_token
@requiere_rol("admin")
def editar_producto(pid):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not payload:
        return jsonify({"error": "Debe enviar al menos un campo",
                        "request_id": _rid()}), 400
    if "cantidad" in payload:
        try:
            payload["cantidad"] = int(payload["cantidad"])
            if payload["cantidad"] < 0:
                return jsonify({"error": "cantidad no puede ser negativa",
                                "request_id": _rid()}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "cantidad debe ser un entero",
                            "request_id": _rid()}), 400
    return proxy_json(
        "PUT", f"{_base()}/productos/{pid}",
        metodo_http=request.method, ruta=request.path,
        payload=payload, headers_origen=dict(request.headers),
        usuario=g.usuario_api, request_id=_rid(),
        evento="inventario.producto.editar", servicio="inventario",
    )


@bp.route("/stock/<int:pid>", methods=["PUT"])
@require_jwt_token
@requiere_rol("admin", "vendedor")
def actualizar_stock(pid):
    """Fija el stock de un producto (el servicio no exige su token: aquí lo cubre el JWT)."""
    payload = request.get_json(silent=True) or {}
    rid = _rid()
    if payload.get("cantidad") is None:
        return jsonify({"error": "cantidad es requerida", "request_id": rid}), 400
    try:
        cantidad = int(payload["cantidad"])
        if cantidad < 0:
            return jsonify({"error": "cantidad no puede ser negativa",
                            "request_id": rid}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "cantidad debe ser un entero",
                        "request_id": rid}), 400

    return proxy_json(
        "PUT", f"{_base()}/stock/{pid}",
        metodo_http=request.method, ruta=request.path,
        payload={"cantidad": cantidad}, headers_origen=dict(request.headers),
        usuario=g.usuario_api, request_id=rid,
        evento="inventario.stock.actualizar", servicio="inventario",
    )


@bp.route("/stock-bajo/<int:minimo>", methods=["GET"])
@require_jwt_token
@requiere_rol("admin", "vendedor")
def stock_bajo(minimo):
    if minimo < 0:
        return jsonify({"error": "el mínimo no puede ser negativo",
                        "request_id": _rid()}), 400
    return proxy_json(
        "GET", f"{_base()}/stock/bajo/{minimo}",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="inventario.stock_bajo", servicio="inventario",
    )


@bp.route("/proveedores", methods=["GET"])
@require_jwt_token
@requiere_rol("admin", "vendedor")
def listar_proveedores():
    return proxy_json(
        "GET", f"{_base()}/proveedores",
        metodo_http=request.method, ruta=request.path,
        headers_origen=dict(request.headers), usuario=g.usuario_api,
        request_id=_rid(), evento="inventario.proveedores.listar",
        servicio="inventario",
    )
