"""Servicio CLIENTES (puerto 8004). BD propia: librospe_ms_clientes."""
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
bcrypt = Bcrypt(app)

SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "librospe-interno-dev")


def _verifica_token():
    """Valida X-Service-Token para escrituras internas (gateway -> microservicio)."""
    esperado = SERVICE_TOKEN
    enviado = request.headers.get("X-Service-Token", "")
    if not esperado or not enviado or not hmac.compare_digest(enviado, esperado):
        return False
    return True


@app.route("/health")
def health():
    db.session.execute(text("SELECT 1"))
    n = db.session.execute(text("SELECT COUNT(*) FROM clientes")).scalar()
    return jsonify({"status": "OK", "servicio": "clientes", "bd": DB_NAME, "clientes": n})


@app.route("/", methods=["GET"])
def listar():
    rows = db.session.execute(
        text("SELECT id,nombres,apellidos,correo,telefono,dni,departamento,provincia,distrito,estado "
             "FROM clientes ORDER BY id")).mappings().all()
    return jsonify([dict(r) for r in rows])


@app.route("/", methods=["POST"])
def crear():
    """Registro de cliente - dueño de datos es este microservicio (librospe_ms_clientes).
    Gateway debe delegar aqui via HTTP + X-Service-Token, no escribir directo a librospe_db.
    """
    if not _verifica_token():
        return jsonify({"error": "Token de servicio invalido"}), 401

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    # Normaliza campos (acepta email/correo, numero_documento/dni)
    email = (data.get("email") or data.get("correo") or "").strip()
    nombres = (data.get("nombres") or "").strip()
    apellidos = (data.get("apellidos") or "").strip()
    clave = data.get("clave") or ""
    telefono = (data.get("telefono") or None)
    if telefono:
        telefono = telefono.strip() or None
    direccion = (data.get("direccion") or None)
    if direccion:
        direccion = direccion.strip() or None
    departamento = (data.get("departamento") or "").strip()
    provincia = (data.get("provincia") or "").strip()
    distrito = (data.get("distrito") or "").strip()
    tipo_documento = (data.get("tipo_documento") or "DNI").strip().upper()
    numero_documento = (data.get("numero_documento") or data.get("dni") or "").strip() or None
    dni_val = numero_documento if tipo_documento == "DNI" else None
    ce_val = numero_documento if tipo_documento == "CE" else None

    if not email or not nombres or not apellidos or not clave:
        return jsonify({"error": "Faltan campos obligatorios: email, nombres, apellidos, clave"}), 400
    if not departamento or not provincia or not distrito:
        return jsonify({"error": "Ubigeo incompleto: departamento, provincia y distrito requeridos"}), 400

    # Verifica duplicado (en su propia BD)
    existe = db.session.execute(text("SELECT id FROM clientes WHERE correo=:c"), {"c": email}).scalar()
    if existe:
        return jsonify({"error": "El correo ya esta registrado"}), 409

    try:
        hashed = bcrypt.generate_password_hash(clave).decode("utf-8")
        db.session.execute(text("""
            INSERT INTO clientes (dni, ce, nombres, apellidos, correo, telefono, direccion,
                                  departamento, provincia, distrito, clave, estado)
            VALUES (:dni, :ce, :nombres, :apellidos, :correo, :telefono, :direccion,
                    :departamento, :provincia, :distrito, :clave, 1)
        """), {
            "dni": dni_val, "ce": ce_val, "nombres": nombres, "apellidos": apellidos,
            "correo": email, "telefono": telefono, "direccion": direccion,
            "departamento": departamento, "provincia": provincia, "distrito": distrito,
            "clave": hashed
        })
        db.session.commit()
        nuevo_id = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        return jsonify({"ok": True, "id": nuevo_id, "correo": email}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


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
