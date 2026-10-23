"""Autenticación stateless con JWT para el API Gateway de LibrosPE.

Emisión y validación de tokens HS256 con PyJWT. El gateway NO mantiene
sesiones ni cookies: el cliente envía siempre
``Authorization: Bearer <token>``.

Entregables:
- crear_token(...)      -> emite un access token con expiración corta.
- require_jwt_token     -> decorador que valida el token y carga la identidad.
- requiere_rol(...)     -> autorización por rol sobre la identidad ya cargada.
"""
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request


class TokenInvalido(Exception):
    """Token ausente, malformado, expirado o con firma inválida."""

    def __init__(self, detalle, codigo=401):
        super().__init__(detalle)
        self.detalle = detalle
        self.codigo = codigo


def _ajustes():
    """Clave, algoritmo y duración a partir de la configuración de la app."""
    clave = current_app.config.get("JWT_CLAVE") or current_app.config.get("SECRET_KEY")
    if not clave:
        raise TokenInvalido("SECRET_KEY no configurado en el gateway", codigo=500)
    algoritmo = current_app.config.get("JWT_ALGORITMO", "HS256")
    minutos = int(current_app.config.get("JWT_MINUTOS", 60))
    return clave, algoritmo, minutos


def crear_token(usuario_id, rol, correo="", nombre="", minutos=None):
    """Firma un access token JWT con los datos de la identidad."""
    clave, algoritmo, duracion = _ajustes()
    ahora = datetime.now(timezone.utc)
    expira = ahora + timedelta(minutes=minutos or duracion)
    payload = {
        "sub": str(usuario_id),
        "rol": rol or "cliente",
        "correo": correo,
        "nombre": nombre,
        "iat": int(ahora.timestamp()),
        "exp": int(expira.timestamp()),
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    token = jwt.encode(payload, clave, algorithm=algoritmo)
    return token, int((expira - ahora).total_seconds())


def decodificar_token(token):
    """Valida firma, expiración y claims obligatorios; devuelve el payload."""
    clave, algoritmo, _ = _ajustes()
    try:
        payload = jwt.decode(
            token,
            clave,
            algorithms=[algoritmo],
            options={"require": ["exp", "iat", "sub", "typ"]},
        )
    except jwt.ExpiredSignatureError:
        raise TokenInvalido("Token expirado: vuelva a iniciar sesión")
    except jwt.InvalidTokenError:
        raise TokenInvalido("Token inválido o firma no reconocida")
    if payload.get("typ") != "access":
        raise TokenInvalido("Tipo de token no permitido en el gateway")
    return payload


def extraer_bearer():
    """Devuelve el token de la cabecera Authorization o lanza TokenInvalido."""
    cabecera = request.headers.get("Authorization", "")
    if not cabecera:
        raise TokenInvalido("Falta la cabecera Authorization: Bearer <token>")
    if not cabecera.startswith("Bearer "):
        raise TokenInvalido("Formato de autorización inválido (se espera Bearer)")
    token = cabecera[7:].strip()
    if not token:
        raise TokenInvalido("Token vacío en la cabecera Authorization")
    return token


def require_jwt_token(f):
    """Exige un JWT válido y expone la identidad en ``g.usuario_api``."""

    @wraps(f)
    def decorado(*args, **kwargs):
        payload = decodificar_token(extraer_bearer())
        g.usuario_api = {
            "id": payload["sub"],
            "rol": payload.get("rol", ""),
            "correo": payload.get("correo", ""),
            "nombre": payload.get("nombre", ""),
            "jti": payload.get("jti", ""),
        }
        return f(*args, **kwargs)

    return decorado


def requiere_rol(*roles):
    """Autoriza por rol. Usar DESPUÉS de @require_jwt_token."""

    def envoltura(f):
        @wraps(f)
        def decorado(*args, **kwargs):
            usuario = getattr(g, "usuario_api", None)
            if usuario is None:
                raise TokenInvalido("Identidad no resuelta para esta ruta")
            if usuario["rol"] not in roles:
                return (
                    jsonify(
                        {
                            "error": "No tiene permisos para esta operación",
                            "rol_requerido": list(roles),
                            "rol_actual": usuario["rol"],
                        }
                    ),
                    403,
                )
            return f(*args, **kwargs)

        return decorado

    return envoltura


def usuario_actual():
    """Identidad cargada por @require_jwt_token (o None)."""
    return getattr(g, "usuario_api", None)
