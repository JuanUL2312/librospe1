"""Configuracion comun de las pruebas.

Las pruebas usan una base MySQL/MariaDB local (Docker o el servicio de CI).
Si no hay base disponible, las que la necesitan se saltan (skip).
"""
import os
import pathlib
import sys

import pytest

WWW = pathlib.Path(__file__).resolve().parent.parent / "www"
sys.path.insert(0, str(WWW))

# Variables de entorno MINIMAS para poder importar la app.
# (la app solo necesita que existan; no conecta al importarla)
os.environ.setdefault("SECRET_KEY", "pruebas-secret-key")
os.environ.setdefault("DB_USER", os.environ.get("TEST_DB_USER", "root"))
os.environ.setdefault("DB_PASSWORD", os.environ.get("TEST_DB_PASSWORD", "dev"))
os.environ.setdefault("DB_HOST", os.environ.get("TEST_DB_HOST", "127.0.0.1"))
os.environ.setdefault("DB_PORT", os.environ.get("TEST_DB_PORT", "3306"))
os.environ.setdefault("DB_NAME", os.environ.get("TEST_DB_NAME", "librospe_db"))
os.environ.setdefault("MS_VENTAS_DB", "librospe_ms_ventas")
os.environ.setdefault("MS_INVENTARIO_DB", "librospe_ms_inventario")
os.environ.setdefault("MS_USUARIOS_DB", "librospe_ms_usuarios")
os.environ.setdefault("MS_CLIENTES_DB", "librospe_ms_clientes")
os.environ.setdefault("SERVICE_TOKEN", "librospe-interno-dev")
os.environ.setdefault("MAPA_TIENDA_LAT", "-12.06586288155065")
os.environ.setdefault("MAPA_TIENDA_LNG", "-75.21539735474676")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.pop("AMQP_URL", None)     # en pruebas no hay broker


@pytest.fixture(scope="session")
def app():
    from app import app as flask_app
    return flask_app


@pytest.fixture(scope="session")
def db_con_datos(app):
    """Base de datos de pruebas (o None si no hay MySQL disponible)."""
    from sqlalchemy import text
    with app.app_context():
        try:
            db = __import__("app").db
            db.session.execute(text("SELECT 1"))
            return db
        except Exception as e:  # pragma: no cover
            pytest.skip(f"no hay base de datos disponible: {str(e)[:120]}")
