"""Prepara la base de datos de pruebas: crea el esquema en las 5 bases.

En CI (y en local con Docker) se ejecuta antes de pytest para que las
plantillas y rutas que consultan datos tengan tablas donde consultar.
"""
import os
import pathlib
import sys

WWW = pathlib.Path(__file__).resolve().parent.parent / "www"
sys.path.insert(0, str(WWW))
os.environ.setdefault("SECRET_KEY", "pruebas-secret-key")
os.environ.setdefault("DB_USER", os.environ.get("TEST_DB_USER", "root"))
os.environ.setdefault("DB_PASSWORD", os.environ.get("TEST_DB_PASSWORD", "dev"))
os.environ.setdefault("DB_HOST", os.environ.get("TEST_DB_HOST", "127.0.0.1"))
os.environ.setdefault("DB_PORT", os.environ.get("TEST_DB_PORT", "3306"))
os.environ.setdefault("DB_NAME", os.environ.get("TEST_DB_NAME", "librospe_db"))

from app import app, db  # noqa: E402
from sqlalchemy import text  # noqa: E402

BASES = {
    "ventas": "librospe_ms_ventas",
    "inventario": "librospe_ms_inventario",
    "usuarios": "librospe_ms_usuarios",
    "clientes": "librospe_ms_clientes",
}

with app.app_context():
    # Cada tabla se crea SOLO en la base de su microservicio (bind).
    for bind, nombre in BASES.items():
        try:
            motor = db.get_engine(bind=bind)
        except Exception as e:
            print(f"  ! no se pudo obtener el bind {bind}: {e}")
            continue
        creadas = 0
        for mapper in db.Model.registry.mappers:
            if mapper.local_table is None:
                continue
            if getattr(mapper.class_, "__bind_key__", None) != bind:
                continue
            mapper.local_table.create(bind=motor, checkfirst=True)
            creadas += 1
        n = db.session.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()"
        )).scalar()
        print(f"  {nombre}: {creadas} tablas del microservicio ({n} en total)")
