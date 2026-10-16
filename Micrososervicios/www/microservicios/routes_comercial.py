"""Microservicio COMERCIAL / VENTAS: pedidos y ventas.

Blueprint en ``/api/comercial``. Lee SOLO de su base de datos (bind
``ventas``): tablas ``comercial_pedidos``, ``comercial_detalle_pedido``
y ``comercial_ventas``. Para obtener stock se conecta con inventario
via HTTP interno (servicio a servicio) usando X-Service-Token.
"""
import json
from urllib.request import Request, urlopen

from flask import current_app, jsonify, request, session
from sqlalchemy import text

from . import comercial_bp, es_llamada_a_si_mismo, get_db, get_login_required, get_service_engine

db = get_db()
login_required = get_login_required()
motor_ventas = get_service_engine("ventas")


def _consultar_inventario(producto_id, cantidad):
    """Pide stock al microservicio INVENTARIO.

    Con servicios realmente separados (local: procesos en 8001-8004) usa
    HTTP + X-Service-Token. En produccion todo corre en un unico worker
    uWSGI: llamar por HTTP a la propia URL se autobloquearia (el worker
    quedaria esperando su propia respuesta hasta el timeout), asi que en ese
    caso se ejecuta la MISMA logica de inventario en proceso.
    """
    url = "{}/api/inventario/_verificar-stock/{}/{}".format(
        current_app.config.get("MS_INVENTARIO_URL", "http://127.0.0.1:8001"),
        producto_id, cantidad)

    if es_llamada_a_si_mismo(url):
        from .routes_inventario import verificar_stock

        resultado = verificar_stock(producto_id, cantidad)
        if resultado is None:
            raise LookupError("Producto no encontrado")
        resultado["via"] = "en proceso (misma app: evita el autobloqueo del worker)"
        return resultado

    req = Request(url, headers={"X-Service-Token": current_app.config["SERVICE_TOKEN"]})
    with urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


@comercial_bp.route("/pedidos", methods=["GET"])
@login_required
def api_comercial_pedidos():
    """Obtener todos los pedidos del microservicio ventas."""
    try:
        pedidos = db.session.execute(text("""
            SELECT * FROM comercial_pedidos
            ORDER BY fecha_pedido DESC
        """), bind_arguments={"bind": motor_ventas}).mappings().all()

        return jsonify([dict(p) for p in pedidos])
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@comercial_bp.route("/pedidos/<int:id>", methods=["GET"])
@login_required
def api_comercial_pedido(id):
    """Obtener un pedido especifico con sus detalles."""
    try:
        pedido = db.session.execute(text("""
            SELECT * FROM comercial_pedidos WHERE id = :id
        """), {"id": id}, bind_arguments={"bind": motor_ventas}).mappings().first()

        if not pedido:
            return jsonify({"error": "Pedido no encontrado"}), 404

        detalles = db.session.execute(text("""
            SELECT * FROM comercial_detalle_pedido WHERE pedido_id = :id
        """), {"id": id}, bind_arguments={"bind": motor_ventas}).mappings().all()

        pedido_dict = dict(pedido)
        pedido_dict["detalles"] = [dict(d) for d in detalles]

        return jsonify(pedido_dict)
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@comercial_bp.route("/pedidos/<int:id>/estado", methods=["PUT"])
@login_required
def api_comercial_actualizar_estado(id):
    """Actualizar el estado de un pedido (solo administrador)."""
    if session.get("rol") != "administrador":
        return jsonify({"error": "No autorizado"}), 403

    try:
        data = request.get_json(silent=True) or {}
        estado = data.get("estado")

        if not estado:
            return jsonify({"error": "Estado requerido"}), 400

        result = db.session.execute(text("""
            UPDATE comercial_pedidos
            SET estado = :estado
            WHERE id = :id
        """), {"estado": estado, "id": id}, bind_arguments={"bind": motor_ventas})

        db.session.commit()

        if result.rowcount == 0:
            return jsonify({"error": "Pedido no encontrado"}), 404

        return jsonify({"success": True, "message": "Estado actualizado"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@comercial_bp.route("/ventas", methods=["GET"])
@login_required
def api_comercial_ventas():
    """Obtener todas las ventas del microservicio ventas."""
    try:
        ventas = db.session.execute(text("""
            SELECT * FROM comercial_ventas
            ORDER BY fecha_venta DESC
        """), bind_arguments={"bind": motor_ventas}).mappings().all()

        return jsonify([dict(v) for v in ventas])
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@comercial_bp.route("/validar-stock/<int:producto_id>/<int:cantidad>", methods=["GET"])
@login_required
def api_comercial_validar_stock(producto_id, cantidad):
    """DEMO de integracion: VENTAS consulta a INVENTARIO por HTTP.

    Pedir stock a inventario con su propria BD a traves de su API interna,
    sin tocar su base de datos directamente.
    """
    try:
        resultado = _consultar_inventario(producto_id, cantidad)
        via = resultado.pop("via", "HTTP + X-Service-Token")
        return jsonify({
            "origen": "comercial (servicio ventas)",
            "consulto_a": "inventario ({})".format(via),
            "respuesta": resultado
        })
    except Exception as e:
        return jsonify({
            "origen": "comercial (servicio ventas)",
            "error": "inventario no disponible",
            "detalle": str(e)
        }), 503