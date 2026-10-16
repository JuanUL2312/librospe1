"""Microservicio INVENTARIO: productos y stock.

Blueprint en ``/api/inventario``. Lee SOLO de su base de datos (bind
``inventario``): tablas ``inventario_productos`` e ``inventario_categorias``.
El endpoint ``_verificar-stock`` es interno: lo consumen otros servicios
(ventas) via HTTP con token, demostrando la conexion entre microservicios.
"""
from flask import jsonify, request, session
from sqlalchemy import text

from . import inventario_bp, get_db, get_login_required, get_service_engine, servicio_requerido

db = get_db()
login_required = get_login_required()
motor_inventario = get_service_engine("inventario")


@inventario_bp.route("/productos", methods=["GET"])
@login_required
def api_inventario_productos():
    """Obtener todos los productos del microservicio inventario."""
    try:
        productos = db.session.execute(text("""
            SELECT * FROM inventario_productos
            ORDER BY nombre
        """), bind_arguments={"bind": motor_inventario}).mappings().all()

        return jsonify([dict(p) for p in productos])
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@inventario_bp.route("/productos/<int:id>", methods=["GET"])
@login_required
def api_inventario_producto(id):
    """Obtener un producto especifico."""
    try:
        producto = db.session.execute(text("""
            SELECT * FROM inventario_productos WHERE id = :id
        """), {"id": id}, bind_arguments={"bind": motor_inventario}).mappings().first()

        if not producto:
            return jsonify({"error": "Producto no encontrado"}), 404

        return jsonify(dict(producto))
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@inventario_bp.route("/stock/<int:id>", methods=["PUT"])
@login_required
def api_inventario_actualizar_stock(id):
    """Actualizar el stock de un producto (solo administrador)."""
    if session.get("rol") not in ["administrador"]:
        return jsonify({"error": "No autorizado"}), 403

    try:
        data = request.get_json(silent=True) or {}
        cantidad = data.get("cantidad")

        if cantidad is None:
            return jsonify({"error": "Cantidad requerida"}), 400

        result = db.session.execute(text("""
            UPDATE inventario_productos
            SET cantidad = :cantidad
            WHERE id = :id
        """), {"cantidad": cantidad, "id": id}, bind_arguments={"bind": motor_inventario})

        db.session.commit()

        if result.rowcount == 0:
            return jsonify({"error": "Producto no encontrado"}), 404

        return jsonify({"success": True, "message": "Stock actualizado"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@inventario_bp.route("/stock/bajo/<int:minimo>", methods=["GET"])
@login_required
def api_inventario_bajo_stock(minimo):
    """Obtener productos con stock menor al minimo indicado."""
    try:
        productos = db.session.execute(text("""
            SELECT * FROM inventario_productos
            WHERE cantidad < :minimo
            ORDER BY cantidad
        """), {"minimo": minimo}, bind_arguments={"bind": motor_inventario}).mappings().all()

        return jsonify([dict(p) for p in productos])
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@inventario_bp.route("/verificar-stock/<int:id>/<int:cantidad>", methods=["GET"])
@login_required
def api_inventario_verificar_stock(id, cantidad):
    """Verificar si hay stock disponible para una cantidad solicitada."""
    try:
        producto = db.session.execute(text("""
            SELECT cantidad FROM inventario_productos WHERE id = :id
        """), {"id": id}, bind_arguments={"bind": motor_inventario}).mappings().first()

        if not producto:
            return jsonify({"error": "Producto no encontrado"}), 404

        disponible = producto["cantidad"] >= cantidad

        return jsonify({
            "producto_id": id,
            "disponible": disponible,
            "stock_actual": producto["cantidad"],
            "cantidad_solicitada": cantidad
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


def verificar_stock(producto_id, cantidad):
    """Stock de un producto leído de la BD PROPIA de inventario (bind 'inventario').

    Devuelve el mismo diccionario que responde el endpoint interno
    ``_verificar-stock``, o ``None`` si el producto no existe. Lo usan tanto
    el endpoint HTTP (para otros servicios) como la resolución en proceso
    cuando ventas e inventario viven en el mismo worker (evita el autobloqueo
    de una llamada HTTP a sí mismo).
    """
    producto = db.session.execute(text("""
        SELECT cantidad FROM inventario_productos WHERE id = :id
    """), {"id": producto_id}, bind_arguments={"bind": motor_inventario}).mappings().first()

    if not producto:
        return None

    return {
        "servicio": "inventario",
        "producto_id": producto_id,
        "disponible": producto["cantidad"] >= cantidad,
        "stock_actual": producto["cantidad"],
        "cantidad_solicitada": cantidad,
    }


@inventario_bp.route("/_verificar-stock/<int:id>/<int:cantidad>", methods=["GET"])
@servicio_requerido
def api_inventario_interno_verificar_stock(id, cantidad):
    """ENDOPOINT INTERNO (token): lo usa el microservicio VENTAS por HTTP.

    No requiere sesion de usuario sino X-Service-Token.
    """
    try:
        resultado = verificar_stock(id, cantidad)
        if resultado is None:
            return jsonify({"error": "Producto no encontrado"}), 404
        return jsonify(resultado)
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500