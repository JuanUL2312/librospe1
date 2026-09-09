"""Microservicio MONITOR: health check y estado de los servicios.

Blueprint expuesto en ``/api``. El endpoint ``/health`` verifica la
conectividad con la base de datos y la existencia de las tablas espejo
de los microservicios comercial e inventario.
"""
from datetime import datetime

from flask import current_app, jsonify
from sqlalchemy import text

from . import monitor_bp, get_db

db = get_db()

TABLAS_SERVICIOS = {
    "comercial": "comercial_pedidos",
    "inventario": "inventario_productos",
}


def _nombre_base_datos():
    """Extrae el nombre de la base de datos desde la URI de conexion."""
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    nombre = uri.rsplit("/", 1)[-1]
    return nombre.split("?")[0].split("#")[0]


@monitor_bp.route("/health", methods=["GET"])
def api_health():
    """Verificar el estado de los microservicios."""
    try:
        db.session.execute(text("SELECT 1"))

        estado_servicios = {}
        for servicio, tabla in TABLAS_SERVICIOS.items():
            existe = db.session.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = :schema
                AND table_name = :tabla
            """), {"schema": _nombre_base_datos(), "tabla": tabla}).scalar()

            estado_servicios[servicio] = "active" if existe else "not_configured"

        return jsonify({
            "status": "OK",
            "service": "LibrosPE microservicios",
            "version": "2.0",
            "services": estado_servicios,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "ERROR",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500