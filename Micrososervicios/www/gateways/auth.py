"""Blueprint de autenticación del API Gateway (emisión de JWT).

El gateway puro NO toca ninguna base de datos: valida credenciales
delegando en el microservicio que las posee (usuarios 8003 para el
personal, clientes 8004 para la tienda) con X-Service-Token y emite el
access token con PyJWT.
"""
import uuid

from flask import Blueprint, jsonify, request

from jwt_auth import crear_token, decodificar_token, extraer_bearer
from jwt_auth import require_jwt_token

from . import auditoria
from .proxy import ServicioError, ServicioNoDisponible, reenviar, url_servicio

bp = Blueprint("api_auth", __name__, url_prefix="/api/v1/auth")


# Destino del login según el tipo de cuenta:
# "usuario" -> personal del sistema (usuarios_sistema, 8003)
# "cliente" -> clientes de la tienda (tabla clientes, 8004)
DESTINOS_LOGIN = {
    "usuario": ("MS_USUARIOS_URL", "http://127.0.0.1:8003", "usuarios"),
    "cliente": ("MS_CLIENTES_URL", "http://127.0.0.1:8004", "clientes"),
}


@bp.route("/login", methods=["POST"])
def login():
    """Valida credenciales contra el microservicio indicado y emite JWT."""
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    datos = request.get_json(silent=True) or {}
    tipo = str(datos.get("tipo") or "usuario").strip().lower()
    correo = str(datos.get("correo") or datos.get("email") or "").strip().lower()
    clave = str(datos.get("clave") or "")

    if tipo not in DESTINOS_LOGIN:
        return jsonify({"error": "tipo debe ser 'usuario' o 'cliente'",
                        "request_id": rid}), 400
    if not correo or not clave:
        return jsonify({"error": "correo y clave son requeridos",
                        "request_id": rid}), 400
    if len(correo) > 120 or len(clave) > 200:
        return jsonify({"error": "Datos demasiado largos",
                        "request_id": rid}), 400

    clave_config, destino, nombre_servicio = DESTINOS_LOGIN[tipo]
    base = url_servicio(clave_config, destino)
    intento = {"correo": correo, "email": correo, "clave": clave}
    try:
        resp = reenviar("POST", f"{base}/validar-credenciales",
                        payload=intento, headers_origen=dict(request.headers),
                        request_id=rid, servicio=nombre_servicio)
    except ServicioNoDisponible as e:
        auditoria.registrar("auth.login", request.method, request.path, 503,
                            payload=intento, request_id=rid, detalle=e.detalle)
        return jsonify({"error": f"Servicio de {nombre_servicio} no disponible",
                        "detalle": e.detalle, "request_id": rid}), 503
    except ServicioError as e:
        auditoria.registrar("auth.login", request.method, request.path, 502,
                            payload=intento, request_id=rid, detalle=e.detalle)
        return jsonify({"error": "Fallo interno validando credenciales",
                        "request_id": rid}), 502

    if resp.status_code == 401:
        auditoria.registrar("auth.login", request.method, request.path, 401,
                            payload=intento, request_id=rid,
                            detalle="credenciales inválidas")
        # Mensaje único: no se revela si el correo existe o no.
        return jsonify({"error": "Credenciales inválidas",
                        "request_id": rid}), 401
    if resp.status_code == 403:
        auditoria.registrar("auth.login", request.method, request.path, 403,
                            payload=intento, request_id=rid,
                            detalle="cuenta deshabilitada")
        return jsonify({"error": "Cuenta deshabilitada",
                        "request_id": rid}), 403
    if resp.status_code != 200:
        auditoria.registrar("auth.login", request.method, request.path, 502,
                            payload=intento, request_id=rid,
                            detalle=f"respuesta inesperada {resp.status_code}")
        return jsonify({"error": "No se pudo validar la sesión",
                        "request_id": rid}), 502

    try:
        identidad = resp.json()
    except ValueError:
        return jsonify({"error": f"Respuesta inválida del servicio de {nombre_servicio}",
                        "request_id": rid}), 502

    token, segundos = crear_token(
        usuario_id=identidad["id"],
        rol=identidad.get("rol", "cliente"),
        correo=identidad.get("correo", correo),
        nombre=identidad.get("nombre", "").strip(),
    )
    auditoria.registrar("auth.login", request.method, request.path, 200,
                        usuario={"id": identidad["id"],
                                 "rol": identidad.get("rol")},
                        payload=intento, request_id=rid,
                        detalle="token emitido")
    return jsonify({
        "token": token,
        "tipo": "Bearer",
        "expira_en": segundos,
        "usuario": {
            "id": identidad["id"],
            "nombre": identidad.get("nombre", ""),
            "correo": identidad.get("correo", correo),
            "rol": identidad.get("rol", ""),
        },
        "request_id": rid,
    }), 200


@bp.route("/refresh", methods=["POST"])
@require_jwt_token
def refrescar():
    """Emite un token nuevo a partir de uno aún válido (sin expirar)."""
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    payload = decodificar_token(extraer_bearer())  # ya válido por decorador
    token, segundos = crear_token(
        usuario_id=payload["sub"],
        rol=payload.get("rol", ""),
        correo=payload.get("correo", ""),
        nombre=payload.get("nombre", ""),
    )
    return jsonify({"token": token, "tipo": "Bearer",
                    "expira_en": segundos, "request_id": rid}), 200


@bp.route("/logout", methods=["POST"])
@require_jwt_token
def logout():
    """Cierre de sesión en el cliente.

    Con autenticación stateless el gateway no revoca tokens: la protección
    es la vida corta del access token (JWT_MINUTOS) y que el frontend lo
    elimine. Documentado a propósito para no prometer una revocación que
    no existe.
    """
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    from jwt_auth import usuario_actual

    auditoria.registrar("auth.logout", request.method, request.path, 200,
                        usuario=usuario_actual(), request_id=rid,
                        detalle="token válido; el cliente debe descartarlo")
    return jsonify({"ok": True,
                    "nota": "Elimine el token almacenado en el cliente; "
                            "el token emitido sigue válido hasta expirar",
                    "request_id": rid}), 200
