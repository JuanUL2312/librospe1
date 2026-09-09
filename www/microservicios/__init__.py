"""Paquete de microservicios de LibrosPE.

Separa los dominios de negocio en blueprints Flask independientes:

- ``comercial``  -> /api/comercial  (pedidos y ventas)
- ``inventario`` -> /api/inventario (productos y stock)
- ``monitor``    -> /api           (health check de los servicios)

Las dependencias compartidas con la aplicacion principal (``db`` y el
decorador ``login_required``) se inyectan mediante :func:`register_microservicios`,
evitando imports circulares entre ``app.py`` y este paquete.
"""
from flask import Blueprint

_db = None
_login_required = None

comercial_bp = Blueprint("comercial", __name__, url_prefix="/api/comercial")
inventario_bp = Blueprint("inventario", __name__, url_prefix="/api/inventario")
monitor_bp = Blueprint("monitor", __name__, url_prefix="/api")


def register_microservicios(app, database, login_required):
    """Registra los blueprints de microservicios en la aplicacion.

    :param app: instancia de Flask principal.
    :param database: instancia de SQLAlchemy compartida.
    :param login_required: decorador de autenticacion del monolito.
    """
    global _db, _login_required
    _db = database
    _login_required = login_required

    from . import routes_monitor, routes_comercial, routes_inventario

    app.register_blueprint(comercial_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(monitor_bp)


def get_db():
    """Devuelve la instancia de SQLAlchemy compartida (inyectada)."""
    return _db


def get_login_required():
    """Devuelve el decorador de autenticacion compartido (inyectado)."""
    return _login_required