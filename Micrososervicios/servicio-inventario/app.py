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


@app.route("/productos", methods=["POST"])
@servicio_requerido
def crear_producto():
    data = request.get_json(silent=True) or {}
    try:
        # Campos obligatorios
        if not data.get("nombre") or data.get("cantidad") is None or data.get("precio") is None:
            return jsonify({"error": "nombre, cantidad y precio requeridos"}), 400
        res = db.session.execute(text("""
            INSERT INTO inventario_productos (nombre, descripcion, cantidad, proveedor_id, precio, imagen, id_categoria, precio_oferta, destacado, codigo_barras, estado, stock_minimo, stock_maximo, costo)
            VALUES (:nombre, :descripcion, :cantidad, :proveedor_id, :precio, :imagen, :id_categoria, :precio_oferta, :destacado, :codigo_barras, :estado, :stock_minimo, :stock_maximo, :costo)
        """), {
            "nombre": data["nombre"], "descripcion": data.get("descripcion"), "cantidad": int(data["cantidad"]),
            "proveedor_id": data.get("proveedor_id"), "precio": float(data["precio"]), "imagen": data.get("imagen"),
            "id_categoria": data.get("id_categoria"), "precio_oferta": data.get("precio_oferta"), "destacado": int(data.get("destacado",0)),
            "codigo_barras": data.get("codigo_barras"), "estado": int(data.get("estado",1)), "stock_minimo": int(data.get("stock_minimo",5)),
            "stock_maximo": int(data.get("stock_maximo",100)), "costo": data.get("costo")
        })
        db.session.commit()
        nid = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        return jsonify({"ok": True, "id": nid}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/productos/<int:pid>", methods=["PUT"])
@servicio_requerido
def editar_producto(pid):
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "Sin datos"}), 400
    # Construye SET dinámico solo con campos enviados
    permitidos = ["nombre","descripcion","cantidad","proveedor_id","precio","imagen","id_categoria","precio_oferta","destacado","codigo_barras","estado","stock_minimo","stock_maximo","costo"]
    campos = {k: data[k] for k in permitidos if k in data}
    if not campos:
        return jsonify({"error": "Sin campos válidos"}), 400
    set_clause = ", ".join([f"{k}=:{k}" for k in campos.keys()])
    try:
        res = db.session.execute(text(f"UPDATE inventario_productos SET {set_clause} WHERE id=:pid"), {**campos, "pid": pid})
        db.session.commit()
        if res.rowcount == 0:
            return jsonify({"error": "No encontrado"}), 404
        return jsonify({"ok": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/productos/<int:pid>", methods=["DELETE"])
@servicio_requerido
def eliminar_producto(pid):
    try:
        res = db.session.execute(text("DELETE FROM inventario_productos WHERE id=:id"), {"id": pid})
        db.session.commit()
        if res.rowcount == 0:
            return jsonify({"error": "No encontrado"}), 404
        return jsonify({"ok": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/proveedores", methods=["GET"])
def listar_proveedores():
    rows = db.session.execute(text("SELECT * FROM inventario_proveedores ORDER BY nombre")).mappings().all()
    return jsonify([dict(r) for r in rows])

@app.route("/proveedores", methods=["POST"])
@servicio_requerido
def crear_proveedor():
    data = request.get_json(silent=True) or {}
    try:
        if not data.get("nombre") or not data.get("email") or not data.get("contacto"):
            return jsonify({"error": "nombre, email y contacto requeridos"}), 400
        res = db.session.execute(text("""
            INSERT INTO inventario_proveedores (nombre, email, contacto, empresa, ruc_empresa_id, estado)
            VALUES (:nombre, :email, :contacto, :empresa, :ruc_empresa_id, :estado)
        """), {
            "nombre": data["nombre"], "email": data["email"], "contacto": data["contacto"],
            "empresa": data.get("empresa", data["nombre"]), "ruc_empresa_id": data.get("ruc_empresa_id"), "estado": int(data.get("estado",1))
        })
        db.session.commit()
        nid = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        return jsonify({"ok": True, "id": nid}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/proveedores/<int:pid>", methods=["PUT"])
@servicio_requerido
def editar_proveedor(pid):
    data = request.get_json(silent=True) or {}
    permitidos = ["nombre","email","contacto","empresa","ruc_empresa_id","estado"]
    campos = {k: data[k] for k in permitidos if k in data}
    if not campos:
        return jsonify({"error": "Sin campos"}), 400
    set_clause = ", ".join([f"{k}=:{k}" for k in campos.keys()])
    try:
        res = db.session.execute(text(f"UPDATE inventario_proveedores SET {set_clause} WHERE id=:pid"), {**campos, "pid": pid})
        db.session.commit()
        if res.rowcount == 0:
            return jsonify({"error": "No encontrado"}), 404
        return jsonify({"ok": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/proveedores/<int:pid>", methods=["DELETE"])
@servicio_requerido
def eliminar_proveedor(pid):
    try:
        res = db.session.execute(text("DELETE FROM inventario_proveedores WHERE id=:id"), {"id": pid})
        db.session.commit()
        if res.rowcount == 0:
            return jsonify({"error": "No encontrado"}), 404
        return jsonify({"ok": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

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
