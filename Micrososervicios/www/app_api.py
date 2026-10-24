"""API Gateway puro de LibrosPE — fase "100% microservicios".

Gateway JSON sin Jinja2 ni sesiones por cookie:
- Identidad stateless con JWT (Authorization: Bearer).
- Blueprints proxy en www/gateways/ que reenvían a los microservicios.
- Protección CSRF acotada a /api/v1: exige JWT en cabecera (inmune a CSRF
  porque el token no viaja en cookies).
- Manejo consistente de errores en JSON.

La instalación compartida vive en api_gateway_setup.configurar(); este
archivo solo fabrica la app pura (sin la tienda Jinja).

Durante la transición, www/app.py con API_GATEWAY=1 sirve la tienda Y la
API en el mismo proceso (coexistencia); al terminar la migración del
frontend a fetch(), la producción puede cambiar a app_api:app.

Arranque local : python app_api.py
uWSGI producción: app_api:app  (o app:app con API_GATEWAY=1)
"""
import os

from flask import Flask


def cargar_entorno():
    """Carga .env con setdefault: no pisa variables ya definidas por uWSGI."""
    from entorno_ms import cargar_entorno as _cargar_env
    _cargar_env(__file__)


cargar_entorno()


def crear_app() -> Flask:
    """Fabrica del API Gateway puro."""
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY")
    if not app.secret_key:
        raise RuntimeError("SECRET_KEY es obligatoria para el API Gateway")

    from api_gateway_setup import configurar

    configurar(app, integrado=False)
    return app


app = crear_app()


if __name__ == "__main__":
    puerto = int(os.environ.get("GATEWAY_API_PORT", "8000"))
    depurar = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="127.0.0.1", port=puerto, debug=depurar)
