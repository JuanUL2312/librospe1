"""Microservicio INVENTARIO: productos y stock.

Blueprint independiente registrado en la aplicacion principal con prefijo
``/api/inventario``. Todos los endpoints consumen las tablas espejo
``inventario_productos`` y ``inventario_categorias``.
"""
from flask import jsonify, request, session
from sqlalchemy import text

from . import inventario_bp, get_db, get_login_required

db = get_db()
login_required = get_login_required()


@inventario_bp.route("/productos", methods=["GET"])
@login_required
def api_inventario_productos():
    """Obtener todos los productos del microservicio inventario."""
    try:
        productos = db.session.execute(text("""
            SELECT * FROM inventario_productos
            ORDER BY nombre
        """)).mappings().all()

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
        """), {"id": id}).mappings().first()

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
        """), {"cantidad": cantidad, "id": id})

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
        """), {"minimo": minimo}).mappings().all()

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
        """), {"id": id}).mappings().first()

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