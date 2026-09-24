"""Servicio USUARIOS (puerto 8003). BD propia: librospe_ms_usuarios."""
import os
from pathlib import Path
from urllib.parse import quote_plus

import hmac
from flask import Flask, jsonify, request
from flask_bcrypt import Bcrypt
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
app.secret_key = os.environ.get("SECRET_KEY", "dev-usuarios")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("MS_USUARIOS_DB", "librospe_ms_usuarios")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/{DB_NAME}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "librospe-interno-dev")

def _verifica():
    return hmac.compare_digest(request.headers.get("X-Service-Token",""), SERVICE_TOKEN)


@app.route("/health")
def health():
    db.session.execute(text("SELECT 1"))
    n = db.session.execute(text("SELECT COUNT(*) FROM usuarios_sistema")).scalar()
    return jsonify({"status": "OK", "servicio": "usuarios", "bd": DB_NAME, "usuarios": n})


@app.route("/")
def listar():
    rows = db.session.execute(
        text("SELECT id,nombres,apellidos,correo,rol,estado,documento FROM usuarios_sistema ORDER BY id")
    ).mappings().all()
    return jsonify([dict(r) for r in rows])


@app.route("/<int:uid>")
def detalle(uid):
    r = db.session.execute(
        text("SELECT id,nombres,apellidos,correo,rol,estado,documento FROM usuarios_sistema WHERE id=:id"),
        {"id": uid}).mappings().first()
    return (jsonify(dict(r)), 200) if r else (jsonify({"error": "No encontrado"}), 404)


@app.route("/roles")
def roles():
    rows = db.session.execute(text("SELECT id,nombre FROM roles ORDER BY id")).mappings().all()
    return jsonify([dict(r) for r in rows])

@app.route("/", methods=["POST"])
def crear():
    if not _verifica():
        return jsonify({"error":"Token invalido"}),401
    data=request.get_json(silent=True) or {}
    try:
        if not data.get("correo") or not data.get("nombres") or not data.get("apellidos"):
            return jsonify({"error":"correo, nombres y apellidos requeridos"}),400
        # verifica duplicado
        ex=db.session.execute(text("SELECT id FROM usuarios_sistema WHERE correo=:c"),{"c":data["correo"]}).scalar()
        if ex:
            return jsonify({"error":"Correo ya registrado"}),409
        # hash clave
        clave_raw=data.get("clave") or "123456"
        hashed=bcrypt.generate_password_hash(clave_raw).decode("utf-8")
        # rol_id
        rol=data.get("rol","vendedor")
        rol_id=data.get("rol_id")
        if not rol_id:
            r=db.session.execute(text("SELECT id FROM roles WHERE nombre=:n"),{"n":rol}).fetchone()
            rol_id=r[0] if r else 2
        res=db.session.execute(text("""
            INSERT INTO usuarios_sistema (correo, nombres, apellidos, clave, estado, rol_id, rol, documento)
            VALUES (:correo, :nombres, :apellidos, :clave, 1, :rol_id, :rol, :documento)
        """),{
            "correo":data["correo"],"nombres":data["nombres"],"apellidos":data["apellidos"],
            "clave":hashed,"rol_id":rol_id,"rol":rol,"documento":data.get("documento")
        })
        db.session.commit()
        nid=db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        return jsonify({"ok":True,"id":nid}),201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error":str(e)}),500

@app.route("/<int:uid>", methods=["PUT"])
def actualizar(uid):
    if not _verifica():
        return jsonify({"error":"Token invalido"}),401
    data=request.get_json(silent=True) or {}
    permitidos=["nombres","apellidos","correo","rol","documento","estado"]
    campos={k:data[k] for k in permitidos if k in data}
    if "correo" in campos:
        ex=db.session.execute(text("SELECT id FROM usuarios_sistema WHERE correo=:c AND id!=:id"),{"c":campos["correo"],"id":uid}).scalar()
        if ex:
            return jsonify({"error":"Correo duplicado"}),409
    if "clave" in data and data["clave"]:
        campos["clave"]=bcrypt.generate_password_hash(data["clave"]).decode("utf-8")
    if not campos:
        return jsonify({"error":"Sin campos"}),400
    set_clause=",".join([f"{k}=:{k}" for k in campos])
    try:
        res=db.session.execute(text(f"UPDATE usuarios_sistema SET {set_clause} WHERE id=:uid"),{**campos,"uid":uid})
        db.session.commit()
        if res.rowcount==0:
            return jsonify({"error":"No encontrado"}),404
        return jsonify({"ok":True}),200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error":str(e)}),500

@app.route("/<int:uid>", methods=["DELETE"])
def eliminar(uid):
    if not _verifica():
        return jsonify({"error":"Token invalido"}),401
    try:
        res=db.session.execute(text("UPDATE usuarios_sistema SET estado=0 WHERE id=:id"),{"id":uid})
        db.session.commit()
        if res.rowcount==0:
            return jsonify({"error":"No encontrado"}),404
        return jsonify({"ok":True}),200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error":str(e)}),500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003)
