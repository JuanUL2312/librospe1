"""Servicio INVENTARIO (puerto 8001). BD propia: librospe_ms_inventario.

Tablas: inventario_productos, inventario_categorias, inventario_proveedores.
Se comunica con otros servicios SOLO por HTTP + X-Service-Token.
"""
import hmac
import os
from functools import wraps
from pathlib import Path
from urllib.parse import quote_plus

from flask import Flask, jsonify, request
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
app.secret_key = os.environ.get("SECRET_KEY", "dev-inventario")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("MS_INVENTARIO_DB", "librospe_ms_inventario")
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "librospe-interno-dev")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/{DB_NAME}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


def servicio_requerido(f):
    @wraps(f)
    def d(*a, **k):
        if not hmac.compare_digest(request.headers.get("X-Service-Token", ""), SERVICE_TOKEN):
            return jsonify({"error": "Token de servicio invalido"}), 401
        return f(*a, **k)
    return d


@app.route("/health")
def health():
    db.session.execute(text("SELECT 1"))
    n = db.session.execute(text("SELECT COUNT(*) FROM inventario_productos")).scalar()
    return jsonify({"status": "OK", "servicio": "inventario", "bd": DB_NAME, "productos": n})


@app.route("/productos")
def listar():
    rows = db.session.execute(text("SELECT * FROM inventario_productos ORDER BY nombre")).mappings().all()
    return jsonify([dict(r) for r in rows])


@app.route("/productos/<int:pid>")
def detalle(pid):
    r = db.session.execute(
        text("SELECT * FROM inventario_productos WHERE id=:id"), {"id": pid}).mappings().first()
    return (jsonify(dict(r)), 200) if r else (jsonify({"error": "No encontrado"}), 404)


@app.route("/stock/<int:pid>", methods=["PUT"])
def actualizar_stock(pid):
    data = request.get_json(silent=True) or {}
    if data.get("cantidad") is None:
        return jsonify({"error": "Cantidad requerida"}), 400
    res = db.session.execute(
        text("UPDATE inventario_productos SET cantidad=:c WHERE id=:id"),
        {"c": data["cantidad"], "id": pid})
    db.session.commit()
    return jsonify({"success": True}) if res.rowcount else (jsonify({"error": "No encontrado"}), 404)


@app.route("/stock/bajo/<int:minimo>")
def bajo_stock(minimo):
    rows = db.session.execute(
        text("SELECT * FROM inventario_productos WHERE cantidad < :m ORDER BY cantidad"),
        {"m": minimo}).mappings().all()
    return jsonify([dict(r) for r in rows])


@app.route("/verificar-stock/<int:pid>/<int:cant>")
def verificar(pid, cant):
    return _verificar(pid, cant)


@app.route("/_verificar-stock/<int:pid>/<int:cant>")
@servicio_requerido
def verificar_interno(pid, cant):
    r = _verificar(pid, cant).get_json()
    r["servicio"] = "inventario"
    return jsonify(r)


def _verificar(pid, cant):
    r = db.session.execute(
        text("SELECT cantidad FROM inventario_productos WHERE id=:id"),
        {"id": pid}).mappings().first()
    if not r:
        return jsonify({"error": "No encontrado"}), 404
    return jsonify({"producto_id": pid, "disponible": r["cantidad"] >= cant,
                    "stock_actual": r["cantidad"], "cantidad_solicitada": cant})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
