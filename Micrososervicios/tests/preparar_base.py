"""Prepara la base de datos de pruebas: crea el esquema en las 5 bases.

En CI (y en local con Docker) se ejecuta antes de pytest para que las
plantillas y rutas que consultan datos tengan tablas donde consultar.

Uso:  python Micrososervicios/tests/preparar_base.py
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


def _tablas_de(bind):
    """Tablas cuyo modelo pertenece a ese microservicio (incluye espejos)."""
    salida = []
    for mapper in db.Model.registry.mappers:
        if mapper.local_table is None:
            continue
        if getattr(mapper.class_, "__bind_key__", None) == bind:
            salida.append((mapper.class_.__name__, mapper.local_table))
    return salida


def _crear_tabla(con, motor, tabla):
    """Crea la tabla en su base, sin las FK que apuntan a otro microservicio.

    El DDL se arma a mano (no con CreateTable) porque algunas columnas
    declaran claves foraneas hacia tablas que viven en otra base
    (p.ej. usuarios_sistema.rol_id -> roles) y SQLAlchemy no encuentra la
    tabla referenciada al compilar. En produccion esas FK no existen: las
    copias se crean con CREATE TABLE ... LIKE.
    """
    columnas = []
    for col in tabla.columns:
        tipo = col.type.compile(dialect=motor.dialect)
        partes = [f"`{col.name}` {tipo}"]
        if col.primary_key:
            partes.append("PRIMARY KEY")
            if getattr(col, "autoincrement", False) and col.type.__class__.__name__ == "Integer":
                partes.append("AUTO_INCREMENT")
        elif not col.nullable:
            partes.append("NOT NULL")
        if col.default is not None:
            valor = getattr(col.default, "arg", None)
            if valor is not None and isinstance(valor, (int, float, str, bool)):
                partes.append(f"DEFAULT {valor!r}" if isinstance(valor, str) else f"DEFAULT {valor}")
        columnas.append(" ".join(partes))
    ddl = (f"CREATE TABLE IF NOT EXISTS `{tabla.name}` (\n  "
           + ",\n  ".join(columnas)
           + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
    try:
        con.execute(text(ddl))
        return True
    except Exception as e:
        print(f"  ! {tabla.name}: {str(e)[:110]}")
        return False


with app.app_context():
    for bind, nombre in BASES.items():
        try:
            motor = db.get_engine(bind=bind)
        except Exception as e:
            print(f"  ! no se pudo obtener el bind {bind}: {e}")
            continue
        # Las claves foraneas de algunos modelos apuntan a tablas de OTRO
        # microservicio (p.ej. usuarios_sistema.rol_id -> roles). En cada base
        # solo existe su parte, asi que se crea el DDL sin esas FK (igual que
        # hace CREATE TABLE ... LIKE en la migracion real de produccion).
        creadas = 0
        with motor.connect() as con:
            con.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for _clase, tabla in _tablas_de(bind):
                if not _crear_tabla(con, motor, tabla):
                    continue
                creadas += 1
            con.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            n = con.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema=DATABASE()")).scalar()
        print(f"  {nombre}: {creadas} tablas del microservicio ({n} en total)")
