"""Paquete de microservicios de LibrosPE.

Cada modulo de negocio es un Blueprint Flask independiente con SU PROPIA
base de datos (bind de SQLAlchemy) y se comunica con los demas SOLO por
HTTP con token interno (X-Service-Token). No hay SQL cruzado entre BDs.

- ``ventas``     -> /api/comercial   (pedidos y ventas)      BD: bind 'ventas'
- ``inventario`` -> /api/inventario  (productos y stock)     BD: bind 'inventario'
- ``usuarios``   -> /api/usuarios    (usuarios del sistema)  BD: bind 'usuarios'
- ``clientes``   -> /api/clientes    (clientes registrados)  BD: bind 'clientes'
- ``monitor``    -> /api             (health de los 5)       BD: verifica cada bind

Las dependencias compartidas (``db`` y ``login_required``) se inyectan mediante
:func:`register_microservicios`, evitando imports circulares con ``app.py``.
"""
import hmac
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

_app = None
_db = None
_login_required = None

comercial_bp = Blueprint("comercial", __name__, url_prefix="/api/comercial")
inventario_bp = Blueprint("inventario", __name__, url_prefix="/api/inventario")
usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")
clientes_bp = Blueprint("clientes", __name__, url_prefix="/api/clientes")
monitor_bp = Blueprint("monitor", __name__, url_prefix="/api")


def register_microservicios(app, database, login_required):
    """Registra los blueprints de microservicios en la aplicacion.

    :param app: instancia de Flask principal.
    :param database: instancia de SQLAlchemy compartida.
    :param login_required: decorador de autenticacion del monolito.
    """
    global _app, _db, _login_required
    _app = app
    _db = database
    _login_required = login_required

    from . import routes_monitor, routes_comercial, routes_inventario, routes_usuarios, routes_clientes

    app.register_blueprint(comercial_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(monitor_bp)


def get_db():
    """Devuelve la instancia de SQLAlchemy compartida (inyectada)."""
    return _db


def get_login_required():
    """Devuelve el decorador de autenticacion compartido (inyectado)."""
    return _login_required


def get_service_engine(bind_key):
    """Devuelve el engine SQLAlchemy de la base de datos de un microservicio.

    Cada microservicio usa SIEMPRE su propio bind; jamas lee de la BD de otro.
    """
    return _db.get_engine(_app, bind_key)


def servicio_requerido(f):
    """Protege endpoints internos: solo otros microservicios (con token).

    El token se comparte via cabecera ``X-Service-Token`` y se valida con
    hmac.compare_digest para evitar comparaciones vulnerables a timing.
    """
    @wraps(f)
    def decorado(*args, **kwargs):
        enviado = request.headers.get("X-Service-Token", "")
        esperado = current_app.config.get("SERVICE_TOKEN", "")
        if not esperado or not enviado or not hmac.compare_digest(enviado, esperado):
            return jsonify({"error": "Token de servicio invalido"}), 401
        return f(*args, **kwargs)
    return decorado