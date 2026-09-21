"""Microservicio USUARIOS: usuarios del sistema, roles y permisos.

Blueprint en ``/api/usuarios``. Lee SOLO de su base de datos (bind
``usuarios``): tabla ``usuarios_sistema`` (y roles). No comparte la BD
con los demas servicios.
"""
from flask import jsonify
from sqlalchemy import text

from . import usuarios_bp, get_db, get_login_required, get_service_engine

db = get_db()
login_required = get_login_required()
motor_usuarios = get_service_engine("usuarios")


@usuarios_bp.route("", methods=["GET"])
@login_required
def api_usuarios_listar():
    """Obtener todos los usuarios del sistema (microservicio usuarios)."""
    try:
        usuarios = db.session.execute(text("""
            SELECT id, nombres, apellidos, correo, rol, estado, documento
            FROM usuarios_sistema
            ORDER BY id
        """), bind_arguments={"bind": motor_usuarios}).mappings().all()

        return jsonify([dict(u) for u in usuarios])
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@usuarios_bp.route("/<int:usuario_id>", methods=["GET"])
@login_required
def api_usuarios_detalle(usuario_id):
    """Obtener un usuario del sistema especifico."""
    try:
        usuario = db.session.execute(text("""
            SELECT id, nombres, apellidos, correo, rol, estado, documento
            FROM usuarios_sistema WHERE id = :id
        """), {"id": usuario_id}, bind_arguments={"bind": motor_usuarios}).mappings().first()

        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        return jsonify(dict(usuario))
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@usuarios_bp.route("/roles", methods=["GET"])
@login_required
def api_usuarios_roles():
    """Obtener los roles disponibles (microservicio usuarios)."""
    try:
        roles = db.session.execute(text("""
            SELECT id, nombre FROM roles ORDER BY id
        """), bind_arguments={"bind": motor_usuarios}).mappings().all()

        return jsonify([dict(r) for r in roles])
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500