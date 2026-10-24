"""Sondeo corto de /health de los microservicios HTTP (sin reintentos).

Usado por el monitor de la tienda y por GET /api/v1/health?profundo=1.
Timeout 1.5 s: un puerto cerrado responde al instante; no se usa el proxy
de 3s/8s ni su reintento GET (eso alargaría el health hasta ~16 s).
"""
from urllib.error import URLError, HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

TIMEOUT = 1.5

CLAVES_URL = (
    ("inventario", "MS_INVENTARIO_URL", "http://127.0.0.1:8001"),
    ("ventas", "MS_VENTAS_URL", "http://127.0.0.1:8002"),
    ("usuarios", "MS_USUARIOS_URL", "http://127.0.0.1:8003"),
    ("clientes", "MS_CLIENTES_URL", "http://127.0.0.1:8004"),
)


def urls_desde_app(app):
    """Dict nombre -> URL base según la config Flask."""
    return {
        nombre: (app.config.get(clave) or defecto).rstrip("/")
        for nombre, clave, defecto in CLAVES_URL
    }


def es_url_autoreferenciada(url_destino, host_url=""):
    """True si la URL del MS apunta al mismo host:puerto del proceso actual."""
    if not host_url:
        try:
            from flask import has_request_context, request
            if has_request_context():
                host_url = request.host_url
        except Exception:
            return False
    if not host_url:
        return False
    try:
        destino = urlsplit(url_destino)
        propio = urlsplit(host_url)
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


def sondear_uno(url_base, timeout=TIMEOUT, host_url=""):
    """Devuelve 'OK', 'url_autoreferenciada', 'caído/no alcanzable' o 'HTTP N'."""
    base = (url_base or "").rstrip("/")
    if not base:
        return "sin URL"
    if es_url_autoreferenciada(base, host_url=host_url):
        return "url_autoreferenciada"
    url = base + "/health"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            return "OK" if 200 <= resp.status < 300 else f"HTTP {resp.status}"
    except HTTPError as e:
        return f"HTTP {e.code}"
    except (URLError, TimeoutError, OSError):
        return "caído/no alcanzable"


def sondear_http(urls, timeout=TIMEOUT, host_url=""):
    """urls: dict nombre -> URL base. Devuelve dict nombre -> estado."""
    return {
        nombre: sondear_uno(base, timeout=timeout, host_url=host_url)
        for nombre, base in urls.items()
    }
