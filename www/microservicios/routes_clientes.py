"""Microservicio CLIENTES: clientes registrados de la tienda.

Blueprint en ``/api/clientes``. Lee SOLO de su base de datos (bind
``clientes``): tabla ``clientes``. No comparte la BD con los demas
servicios.
"""
from flask import jsonify
from sqlalchemy import text

from . import clientes_bp, get_db, get_login_required, get_service_engine

db = get_db()
login_required = get_login_required()
motor_clientes = get_service_engine("clientes")


@clientes_bp.route("", methods=["GET"])
@login_required
def api_clientes_listar():
    """Obtener todos los clientes del microservicio clientes."""
    try:
        clientes = db.session.execute(text("""
            SELECT id, nombres, apellidos, correo, telefono, dni,
                   departamento, provincia, distrito, estado
            FROM clientes
            ORDER BY id
        """), bind_arguments={"bind": motor_clientes}).mappings().all()

        return jsonify([dict(c) for c in clientes])
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@clientes_bp.route("/<int:cliente_id>", methods=["GET"])
@login_required
def api_clientes_detalle(cliente_id):
    """Obtener un cliente especifico."""
    try:
        cliente = db.session.execute(text("""
            SELECT id, nombres, apellidos, correo, telefono, dni,
                   departamento, provincia, distrito, estado
            FROM clientes WHERE id = :id
        """), {"id": cliente_id}, bind_arguments={"bind": motor_clientes}).mappings().first()

        if not cliente:
            return jsonify({"error": "Cliente no encontrado"}), 404

        return jsonify(dict(cliente))
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@clientes_bp.route("/ubicacion", methods=["GET"])
@login_required
def api_clientes_por_ubicacion():
    """Resumen de clientes agrupados por departamento/provincia/distrito."""
    try:
        resumen = db.session.execute(text("""
            SELECT departamento, provincia, distrito, COUNT(*) AS total
            FROM clientes
            GROUP BY departamento, provincia, distrito
            ORDER BY total DESC
        """), bind_arguments={"bind": motor_clientes}).mappings().all()

        return jsonify([dict(r) for r in resumen])
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500