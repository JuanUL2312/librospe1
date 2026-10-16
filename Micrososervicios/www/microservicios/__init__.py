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
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request

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
    global _db, _login_required
    _db = database
    _login_required = login_required

    # Los blueprints resuelven su motor (get_engine) en el import y ese
    # metodo exige contexto de app. Por eso los imports van dentro de
    # app_context: los binds quedan construidos y cacheados al arrancar.
    with app.app_context():
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
    return _db.get_engine(bind_key)


def _puerto_efectivo(url):
    """Puerto de una URL ya parseada (el explícito o el del esquema)."""
    if url.port:
        return url.port
    return 443 if url.scheme == "https" else 80


def es_llamada_a_si_mismo(url):
    """True si ``url`` apunta a ESTA misma aplicación (mismo host y puerto).

    En producción los microservicios viven dentro del mismo proceso uWSGI
    (``processes = 1``): una llamada HTTP a la propia URL se autobloquearía
    hasta agotar el timeout, porque el único worker estaría ocupado
    esperando su propia respuesta. Quien detecte este caso debe resolverlo
    en proceso en lugar de por HTTP (con servicios realmente separados, en
    cambio, sí se hace la llamada HTTP normal).
    """
    try:
        destino = urlsplit(url)
        propio = urlsplit(request.host_url)
    except ValueError:
        return False
    if not destino.hostname or not propio.hostname:
        return False
    if destino.hostname != propio.hostname:
        return False
    puerto_destino = _puerto_efectivo(destino)
    puerto_propio = _puerto_efectivo(propio)
    if puerto_destino == puerto_propio:
        return True
    # Detrás de un proxy que no propaga el esquema, ``request.host_url`` puede
    # verse como ``http://`` mientras la URL configurada es ``https://`` (o al
    # contrario). Mismo host con solo los puertos por defecto 80/443 sigue
    # siendo esta misma aplicación.
    return {puerto_destino, puerto_propio} <= {80, 443}


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