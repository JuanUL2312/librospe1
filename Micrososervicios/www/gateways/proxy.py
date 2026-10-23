"""Reenvío HTTP del API Gateway a los microservicios internos.

Diseño de resiliencia (sin librerías pesadas, sin hilos):
- Timeout estricto por defecto: 3 s de conexión y 8 s de lectura.
- Sin reintentos automáticos en métodos mutantes (POST/PUT/DELETE) para no
  duplicar operaciones de negocio; los GET pueden reintentar una vez.
- El microservicio NO debe recibir cookies del cliente: solo un conjunto
  explícito de cabeceras (Host, Content-Length y Cookie se descartan a
  propósito porque romperían o filtrarían la llamada interna).
"""
import uuid
from urllib.parse import urlsplit

import requests
from flask import current_app, jsonify, request

from . import auditoria

# (conexión, lectura) en segundos.
TIMEOUT = (3.0, 8.0)

# Cabeceras del cliente que SÍ se propagan al microservicio.
_HEADERS_REENVIAR = (
    "Authorization",
    "Content-Type",
    "Accept",
    "Accept-Language",
    "Idempotency-Key",
    "X-Request-Id",
)

_REINTENTOS_GET = 1


class ServicioNoDisponible(Exception):
    """El microservicio está caído, no responde o no es alcanzable (503)."""

    def __init__(self, servicio, detalle):
        super().__init__(detalle)
        self.servicio = servicio
        self.detalle = detalle


class ServicioError(Exception):
    """El microservicio respondió con un fallo interno o inesperado (502)."""

    def __init__(self, servicio, detalle):
        super().__init__(detalle)
        self.servicio = servicio
        self.detalle = detalle


def _es_llamada_a_si_mismo(url_destino):
    """True si la URL apunta a ESTA misma aplicación (mismo host y puerto).

    En Alwaysdata todo corre en un único worker uWSGI: un forward HTTP a la
    propia URL se autobloquearía hasta agotar el timeout. Este escudo avisa
    con 503 en lugar de colgar el proceso.
    """
    try:
        destino = urlsplit(url_destino)
        propio = urlsplit(request.host_url)
    except ValueError:
        return False
    if not destino.hostname or not propio.hostname:
        return False
    if destino.hostname != propio.hostname:
        return False
    puerto_destino = destino.port or (443 if destino.scheme == "https" else 80)
    puerto_propio = propio.port or (443 if propio.scheme == "https" else 80)
    if puerto_destino == puerto_propio:
        return True
    return {puerto_destino, puerto_propio} <= {80, 443}


def url_servicio(clave_config, valor_por_defecto):
    """URL base de un microservicio desde la configuración."""
    url = (current_app.config.get(clave_config) or valor_por_defecto).rstrip("/")
    return url


def reenviar(metodo, url_interna, payload=None, headers_origen=None,
             usuario=None, request_id=None, servicio="microservicio"):
    """Reenvía la petición al microservicio y devuelve la respuesta cruda.

    Lanza ServicioNoDisponible (503) si el servicio no responde y
    ServicioError (502) ante un fallo inesperado del transporte.
    """
    if _es_llamada_a_si_mismo(url_interna):
        raise ServicioNoDisponible(
            servicio,
            "la URL del microservicio apunta al propio proceso del gateway; "
            "en producción deben correr en procesos/puertos separados",
        )

    cabeceras = {}
    for nombre, valor in (headers_origen or {}).items():
        if nombre.lower() in {h.lower() for h in _HEADERS_REENVIAR}:
            cabeceras[nombre] = valor

    token_interno = current_app.config.get("SERVICE_TOKEN", "")
    if token_interno:
        cabeceras["X-Service-Token"] = token_interno
    cabeceras["X-Request-Id"] = request_id or uuid.uuid4().hex
    if usuario:
        cabeceras["X-Usuario-Id"] = str(usuario.get("id", ""))
        cabeceras["X-Usuario-Rol"] = usuario.get("rol", "")

    intentos = 1 if metodo.upper() != "GET" else _REINTENTOS_GET + 1
    ultimo_error = None
    for _ in range(intentos):
        try:
            return requests.request(
                metodo.upper(),
                url_interna,
                json=payload,
                headers=cabeceras,
                timeout=TIMEOUT,
                allow_redirects=False,
            )
        except (requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout) as e:
            ultimo_error = f"timeout {TIMEOUT[0]:.0f}s/{TIMEOUT[1]:.0f}s: {e}"
        except requests.exceptions.ConnectionError as e:
            ultimo_error = f"sin conexión con {servicio}: {e.__class__.__name__}"
        except requests.exceptions.RequestException as e:
            raise ServicioError(servicio, f"error de transporte: {e}") from e

    raise ServicioNoDisponible(servicio, ultimo_error or "no responde")


def respuesta_pasada(resp):
    """Devuelve al cliente el cuerpo y estado EXACTOS del microservicio."""
    from flask import Response

    tipo = resp.headers.get("Content-Type", "application/json; charset=utf-8")
    encabezados = {}
    for clave in ("X-Request-Id", "Location", "Idempotency-Key"):
        if clave in resp.headers:
            encabezados[clave] = resp.headers[clave]
    return Response(resp.content, status=resp.status_code,
                    content_type=tipo, headers=encabezados)


def proxy_json(metodo_interno, url_interna, *, metodo_http, ruta,
               payload=None, headers_origen=None, usuario=None,
               request_id="", evento="api", servicio="microservicio"):
    """Reenvía al microservicio y devuelve SIEMPRE una respuesta Flask lista.

    - Servicio caído/sin respuesta -> 503 con detalle en español.
    - Fallo de transporte inesperado -> 502 (sin exponer detalles internos).
    - Respuesta 5xx del microservicio -> 502 hacia el cliente final.
    - Éxito o error 4xx: cuerpo y estado EXACTOS del microservicio.
    Cada desenlace queda auditado localmente.
    """
    try:
        resp = reenviar(metodo_interno, url_interna, payload=payload,
                        headers_origen=headers_origen, usuario=usuario,
                        request_id=request_id, servicio=servicio)
    except ServicioNoDisponible as e:
        auditoria.registrar(evento, metodo_http, ruta, 503, usuario=usuario,
                            payload=payload, request_id=request_id,
                            detalle=e.detalle)
        return jsonify({
            "error": f"Servicio de {e.servicio} no disponible",
            "detalle": e.detalle,
            "servicio": e.servicio,
            "request_id": request_id,
        }), 503
    except ServicioError as e:
        auditoria.registrar(evento, metodo_http, ruta, 502, usuario=usuario,
                            payload=payload, request_id=request_id,
                            detalle=e.detalle)
        return jsonify({
            "error": f"El microservicio de {e.servicio} falló de forma inesperada",
            "servicio": e.servicio,
            "request_id": request_id,
        }), 502

    auditoria.registrar(evento, metodo_http, ruta, resp.status_code,
                        usuario=usuario, payload=payload,
                        request_id=request_id,
                        detalle="respuesta del microservicio")
    if resp.status_code >= 500:
        return jsonify({
            "error": f"Error interno del microservicio de {servicio}",
            "servicio": servicio,
            "request_id": request_id,
        }), 502
    return respuesta_pasada(resp)
