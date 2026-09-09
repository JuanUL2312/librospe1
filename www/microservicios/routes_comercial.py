"""Microservicio COMERCIAL: pedidos y ventas.

Blueprint independiente registrado en la aplicacion principal con prefijo
``/api/comercial``. Todos los endpoints consumen las tablas espejo
``comercial_pedidos``, ``comercial_detalle_pedido`` y ``comercial_ventas``.
"""
from flask import jsonify, request, session
from sqlalchemy import text

from . import comercial_bp, get_db, get_login_required

db = get_db()
login_required = get_login_required()


@comercial_bp.route("/pedidos", methods=["GET"])
@login_required
def api_comercial_pedidos():
    """Obtener todos los pedidos del microservicio comercial."""
    try:
        pedidos = db.session.execute(text("""
            SELECT * FROM comercial_pedidos
            ORDER BY fecha_pedido DESC
        """)).mappings().all()

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
        """), {"id": id}).mappings().first()

        if not pedido:
            return jsonify({"error": "Pedido no encontrado"}), 404

        detalles = db.session.execute(text("""
            SELECT * FROM comercial_detalle_pedido WHERE pedido_id = :id
        """), {"id": id}).mappings().all()

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
        """), {"estado": estado, "id": id})

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
    """Obtener todas las ventas del microservicio comercial."""
    try:
        ventas = db.session.execute(text("""
            SELECT * FROM comercial_ventas
            ORDER BY fecha_venta DESC
        """)).mappings().all()

        return jsonify([dict(v) for v in ventas])
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500