"""Configuración reutilizable del API Gateway JWT sobre una app Flask existente.

Dos contextos de uso:

- integrado=False (www/app_api.py): gateway JSON puro; todas las respuestas,
  incluidas las de error, salen en JSON.
- integrado=True  (www/app.py): coexistencia con la tienda Jinja en el MISMO
  proceso (activable con API_GATEWAY=1). En este modo:
    * la protección CSRF del gateway solo actúa bajo /api/v1/ (los formularios
      y AJAX heredados de la tienda conservan su @csrf_protect intactos),
    * los errores HTTP salen en JSON solo bajo /api/ (el resto de la tienda
      conserva el manejo estándar de Flask),
    * no se registran rutas que ya existan (p.ej. /api/health del monitor),
    * los headers de observabilidad solo se añaden a /api/.
"""
import os
import time
import uuid
from datetime import datetime, timezone

from flask import g, jsonify, redirect, request
from werkzeug.exceptions import HTTPException

from jwt_auth import TokenInvalido

METODOS_MUTANTES = {"POST", "PUT", "PATCH", "DELETE"}
PREFIJO_V1 = "/api/v1/"
PREFIJO_API = "/api/"
CSRF_RUTAS_LIBRES = ("/api/v1/auth/login", "/api/v1/clientes/registro")


def _en(ruta, prefijo):
    return (ruta or "/").startswith(prefijo)


def aplicar_config(app, *, integrado=False):
    """Rellena la config del gateway con setdefault: no pisa la config
    ya fijada por la app anfitriona (SECRET_KEY, etc.)."""
    app.config.setdefault("JWT_CLAVE", os.environ.get("JWT_CLAVE") or app.secret_key)
    app.config.setdefault("JWT_ALGORITMO", os.environ.get("JWT_ALGORITMO", "HS256"))
    app.config.setdefault("JWT_MINUTOS", int(os.environ.get("JWT_MINUTOS", "60")))
    app.config.setdefault("SERVICE_TOKEN", os.environ.get("SERVICE_TOKEN", ""))
    # VENTAS = 8002; INVENTARIO = 8001; USUARIOS = 8003; CLIENTES = 8004
    app.config.setdefault("MS_VENTAS_URL",
                          os.environ.get("MS_VENTAS_URL", "http://127.0.0.1:8002"))
    app.config.setdefault("MS_INVENTARIO_URL",
                          os.environ.get("MS_INVENTARIO_URL", "http://127.0.0.1:8001"))
    app.config.setdefault("MS_USUARIOS_URL",
                          os.environ.get("MS_USUARIOS_URL", "http://127.0.0.1:8003"))
    app.config.setdefault("MS_CLIENTES_URL",
                          os.environ.get("MS_CLIENTES_URL", "http://127.0.0.1:8004"))
    app.config.setdefault("CSRF_RUTAS_LIBRES", CSRF_RUTAS_LIBRES)
    if not integrado:
        app.config.setdefault("JSON_SORT_KEYS", False)
    return app


def _instalar_csrf(app):
    """CSRF del gateway, acotado a /api/v1/.

    Rutas de emisión de token (login/registro) pasan sin JWT; el resto exige
    Authorization: Bearer (token en cabecera -> inmune a CSRF por cookie).
    Cualquier otra ruta de la app anfitriona (tienda, /api/comercial heredado...)
    queda fuera de este guard: ya tiene su propia protección.
    """

    @app.before_request
    def proteger_csrf():
        if request.method not in METODOS_MUTANTES:
            return None
        ruta = request.path or "/"
        if not _en(ruta, PREFIJO_V1):
            return None
        if any(ruta.startswith(p) for p in app.config.get("CSRF_RUTAS_LIBRES", ())):
            return None
        if request.headers.get("Authorization", "").startswith("Bearer "):
            return None
        return jsonify({
            "error": "Petición API sin JWT: envíe Authorization: Bearer <token>",
            "ruta": ruta,
        }), 403


def _instalar_observabilidad(app):
    """X-Request-Id / X-Duracion-Ms / nosniff, solo en /api/."""

    @app.before_request
    def marcar_peticion():
        if _en(request.path, PREFIJO_API):
            g.rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
            g.t0 = time.monotonic()
        return None

    @app.after_request
    def responder_cabeceras(resp):
        if _en(request.path, PREFIJO_API):
            resp.headers.setdefault("X-Request-Id", getattr(g, "rid", ""))
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            if hasattr(g, "t0"):
                resp.headers.setdefault(
                    "X-Duracion-Ms", str(int((time.monotonic() - g.t0) * 1000))
                )
        return resp


def _instalar_errores(app, *, integrado):
    @app.errorhandler(TokenInvalido)
    def error_token(e):
        return jsonify({"error": e.detalle, "codigo": e.codigo,
                        "request_id": getattr(g, "rid", "")}), e.codigo

    if integrado:
        # Un solo handler: /api/* responde JSON; el resto de la tienda
        # conserva las respuestas estándar de Flask (HTML de la excepción).
        @app.errorhandler(HTTPException)
        def error_http(e):
            if not _en(request.path, PREFIJO_API):
                return e.get_response(request.environ)
            detalle = {
                400: "Solicitud inválida",
                404: "Ruta no encontrada",
                405: "Método no permitido para esta ruta",
                429: "Demasiadas solicitudes, intente luego",
            }.get(e.code, e.name)
            cuerpo = {"error": detalle, "codigo": e.code,
                      "request_id": getattr(g, "rid", "")}
            if e.code == 404:
                cuerpo["ruta"] = request.path
            if e.code == 405:
                cuerpo["metodo"] = request.method
            return jsonify(cuerpo), e.code
        return

    @app.errorhandler(400)
    def error_400(e):
        return jsonify({"error": "Solicitud inválida",
                        "request_id": getattr(g, "rid", "")}), 400

    @app.errorhandler(404)
    def error_404(e):
        return jsonify({"error": "Ruta no encontrada",
                        "ruta": request.path,
                        "request_id": getattr(g, "rid", "")}), 404

    @app.errorhandler(405)
    def error_405(e):
        return jsonify({"error": "Método no permitido para esta ruta",
                        "metodo": request.method,
                        "request_id": getattr(g, "rid", "")}), 405

    @app.errorhandler(429)
    def error_429(e):
        return jsonify({"error": "Demasiadas solicitudes, intente luego",
                        "request_id": getattr(g, "rid", "")}), 429

    @app.errorhandler(500)
    def error_500(e):
        return jsonify({"error": "Error interno del gateway",
                        "request_id": getattr(g, "rid", "")}), 500


def _cuerpo_salud(app, profundo):
    cuerpo = {
        "status": "OK",
        "servicio": "api-gateway",
        "version": os.environ.get("APP_VERSION", "api-jwt-1.0"),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "jwt_minutos": app.config["JWT_MINUTOS"],
    }
    if profundo:
        from gateways.proxy import ServicioNoDisponible, reenviar

        servicios = {
            "ventas": app.config["MS_VENTAS_URL"],
            "inventario": app.config["MS_INVENTARIO_URL"],
            "usuarios": app.config["MS_USUARIOS_URL"],
            "clientes": app.config["MS_CLIENTES_URL"],
        }
        estado = {}
        for nombre, base in servicios.items():
            try:
                r = reenviar("GET", f"{base.rstrip('/')}/health", servicio=nombre)
                estado[nombre] = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
            except ServicioNoDisponible:
                estado[nombre] = "caído/no alcanzable"
            except Exception:
                estado[nombre] = "error"
        cuerpo["servicios"] = estado
        if any(v != "OK" for v in estado.values()):
            cuerpo["status"] = "DEGRADADO"
    return cuerpo


def _instalar_rutas(app):
    """Health y redirect de expiración, sin pisar rutas ya existentes."""
    existentes = {r.rule for r in app.url_map.iter_rules()}

    if "/api/v1/health" not in existentes:
        @app.route("/api/v1/health")
        def salud_v1():
            return jsonify(_cuerpo_salud(app, request.args.get("profundo") == "1"))

    if "/api/health" not in existentes:
        @app.route("/api/health")
        def salud():
            return jsonify(_cuerpo_salud(app, request.args.get("profundo") == "1"))

    if "/api/login" not in existentes:
        @app.route("/api/login")
        def login_web():
            """Destino del frontend cuando el JWT expira (401 en api_cliente.js)."""
            return redirect("/static/api_demo/index.html")


def configurar(app, *, integrado=False):
    """Instala el API Gateway (blueprints proxy + JWT + CSRF + errores) sobre
    una app Flask existente. Devuelve la misma app."""
    aplicar_config(app, integrado=integrado)

    from gateways import registrar_blueprints

    registrar_blueprints(app)
    _instalar_csrf(app)
    _instalar_observabilidad(app)
    _instalar_errores(app, integrado=integrado)
    _instalar_rutas(app)
    return app
