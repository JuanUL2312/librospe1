"""Servicio CLIENTES (puerto 8004). BD propia: librospe_ms_clientes."""
import os
from pathlib import Path
from urllib.parse import quote_plus

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text


def cargar_entorno():
    for base in (Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent):
        f = base / ".env"
        if f.is_file():
            for linea in f.read_text(encoding="utf-8").splitlines():
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


cargar_entorno()
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-clientes")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("MS_CLIENTES_DB", "librospe_ms_clientes")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/{DB_NAME}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


@app.route("/health")
def health():
    db.session.execute(text("SELECT 1"))
    n = db.session.execute(text("SELECT COUNT(*) FROM clientes")).scalar()
    return jsonify({"status": "OK", "servicio": "clientes", "bd": DB_NAME, "clientes": n})


@app.route("/")
def listar():
    rows = db.session.execute(
        text("SELECT id,nombres,apellidos,correo,telefono,dni,departamento,provincia,distrito,estado "
             "FROM clientes ORDER BY id")).mappings().all()
    return jsonify([dict(r) for r in rows])


@app.route("/<int:cid>")
def detalle(cid):
    r = db.session.execute(
        text("SELECT id,nombres,apellidos,correo,telefono,dni,departamento,provincia,distrito,estado "
             "FROM clientes WHERE id=:id"), {"id": cid}).mappings().first()
    return (jsonify(dict(r)), 200) if r else (jsonify({"error": "No encontrado"}), 404)


@app.route("/ubicacion")
def ubicacion():
    rows = db.session.execute(
        text("SELECT departamento,provincia,distrito,COUNT(*) AS total FROM clientes "
             "GROUP BY departamento,provincia,distrito ORDER BY total DESC")).mappings().all()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8004)
