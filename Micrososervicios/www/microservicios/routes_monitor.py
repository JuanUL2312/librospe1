"""Microservicio MONITOR: health check de TODOS los servicios.

Blueprint expuesto en ``/api``. El endpoint ``/health`` verifica la
conectividad con cada base de datos de microservicio (bind) y la
existencia de su tabla representativa. Cada servicio reporta en que
BD y schema vive.
"""
from datetime import datetime

from flask import jsonify
from sqlalchemy import text

from . import monitor_bp, get_db, get_service_engine

db = get_db()

TABLAS_SERVICIOS = {
    "ventas": {"tabla": "comercial_pedidos", "bind": "ventas"},
    "inventario": {"tabla": "inventario_productos", "bind": "inventario"},
    "usuarios": {"tabla": "usuarios_sistema", "bind": "usuarios"},
    "clientes": {"tabla": "clientes", "bind": "clientes"},
}


def _nombre_base_datos(bind_key):
    """Extrae el nombre de la BD (schema) del engine de un servicio."""
    return get_service_engine(bind_key).url.database


def _estado_mensajeria():
    """Estado del agente de mensajes (RabbitMQ) y del outbox de respaldo."""
    try:
        from mensajeria import estado as estado_mensajeria
        info = estado_mensajeria()
        return {
            "broker": "conectado" if info.get("broker") else (
                "sin configurar" if not info.get("broker_configurado", True) else "no disponible"),
            "eventos_publicados": info.get("publicados", 0),
            "pendientes_outbox": info.get("en_outbox", 0),
            "ultimo_evento": info.get("ultimo_evento"),
            "ultimo_error": (info.get("ultimo_error") or "")[:120],
        }
    except Exception as e:
        return {"broker": "error", "detalle": str(e)[:120]}


@monitor_bp.route("/health", methods=["GET"])
def api_health():
    """Verificar el estado de los microservicios y sus BDs."""
    try:
        db.session.execute(text("SELECT 1"))

        estado_servicios = {}
        for servicio, cfg in TABLAS_SERVICIOS.items():
            motor = get_service_engine(cfg["bind"])
            existe = db.session.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = :schema AND table_name = :tabla
            """), {"schema": motor.url.database, "tabla": cfg["tabla"]}).scalar()

            estado_servicios[servicio] = "active" if existe else "not_configured"

        return jsonify({
            "status": "OK",
            "service": "LibrosPE microservicios",
            "version": "3.0",
            "bd_por_servicio": {
                servicio: _nombre_base_datos(cfg["bind"])
                for servicio, cfg in TABLAS_SERVICIOS.items()
            },
            "services": estado_servicios,
            "agente_mensajes": _estado_mensajeria(),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "ERROR",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500