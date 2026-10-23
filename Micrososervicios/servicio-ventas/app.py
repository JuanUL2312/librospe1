"""Servicio VENTAS/COMERCIAL (puerto 8002). BD propia: librospe_ms_ventas.

Tablas: comercial_pedidos, comercial_detalle_pedido, comercial_ventas.
Valida stock consultando a INVENTARIO por HTTP + token (nunca toca su BD).
"""
import hmac
import json
import os
from functools import wraps
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

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
app.secret_key = os.environ.get("SECRET_KEY", "dev-ventas")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("MS_VENTAS_DB", "librospe_ms_ventas")
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "librospe-interno-dev")
INVENTARIO_URL = os.environ.get("MS_INVENTARIO_URL", "http://127.0.0.1:8001")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/{DB_NAME}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


@app.route("/health")
def health():
    db.session.execute(text("SELECT 1"))
    n = db.session.execute(text("SELECT COUNT(*) FROM comercial_pedidos")).scalar()
    return jsonify({"status": "OK", "servicio": "ventas", "bd": DB_NAME, "pedidos": n})


@app.route("/pedidos")
def pedidos():
    rows = db.session.execute(
        text("SELECT * FROM comercial_pedidos ORDER BY fecha_pedido DESC")).mappings().all()
    return jsonify([dict(r) for r in rows])


@app.route("/pedidos/<int:pid>")
def pedido(pid):
    p = db.session.execute(
        text("SELECT * FROM comercial_pedidos WHERE id=:id"), {"id": pid}).mappings().first()
    if not p:
        return jsonify({"error": "No encontrado"}), 404
    det = db.session.execute(
        text("SELECT * FROM comercial_detalle_pedido WHERE pedido_id=:id"),
        {"id": pid}).mappings().all()
    d = dict(p)
    d["detalles"] = [dict(x) for x in det]
    return jsonify(d)


@app.route("/pedidos/<int:pid>/estado", methods=["PUT"])
def estado(pid):
    estado = (request.get_json(silent=True) or {}).get("estado")
    if not estado:
        return jsonify({"error": "Estado requerido"}), 400
    res = db.session.execute(
        text("UPDATE comercial_pedidos SET estado=:e WHERE id=:id"), {"e": estado, "id": pid})
    db.session.commit()
    return jsonify({"success": True}) if res.rowcount else (jsonify({"error": "No encontrado"}), 404)


@app.route("/ventas")
def ventas():
    rows = db.session.execute(
        text("SELECT * FROM comercial_ventas ORDER BY fecha_venta DESC")).mappings().all()
    return jsonify([dict(r) for r in rows])


@app.route("/validar-stock/<int:pid>/<int:cant>")
def validar(pid, cant):
    """DEMO servicio-a-servicio: ventas -> inventario por HTTP + token."""
    try:
        req = Request(f"{INVENTARIO_URL}/_verificar-stock/{pid}/{cant}",
                      headers={"X-Service-Token": SERVICE_TOKEN})
        with urlopen(req, timeout=5) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        return jsonify({"origen": "ventas", "consulto_a": "inventario (HTTP+token)", "respuesta": r})
    except Exception as e:
        return jsonify({"origen": "ventas", "error": "inventario no disponible",
                        "detalle": str(e)}), 503


def _verifica_token():
    return hmac.compare_digest(request.headers.get("X-Service-Token", ""), SERVICE_TOKEN)

@app.route("/pedidos", methods=["POST"])
def crear_pedido():
    if not _verifica_token():
        return jsonify({"error": "Token invalido"}), 401
    data = request.get_json(silent=True) or {}
    try:
        if not data.get("cliente_id"):
            return jsonify({"error": "cliente_id requerido"}), 400
        res = db.session.execute(text("""
            INSERT INTO comercial_pedidos (cliente_id, fecha_pedido, estado, total, direccion_entrega, tipo_entrega, nota)
            VALUES (:cliente_id, NOW(), :estado, :total, :direccion_entrega, :tipo_entrega, :nota)
        """), {
            "cliente_id": data["cliente_id"], "estado": data.get("estado","pendiente"),
            "total": data.get("total",0), "direccion_entrega": data.get("direccion_entrega"),
            "tipo_entrega": data.get("tipo_entrega"), "nota": data.get("nota")
        })
        # Antes del commit (misma transaccion/conexion): LAST_INSERT_ID() es por-conexion.
        nid = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        db.session.commit()
        # Detalles si vienen
        for det in data.get("detalles", []):
            db.session.execute(text("""
                INSERT INTO comercial_detalle_pedido (pedido_id, producto_id, cantidad, precio_unitario, subtotal)
                VALUES (:pedido_id, :producto_id, :cantidad, :precio_unitario, :subtotal)
            """), {
                "pedido_id": nid, "producto_id": det["producto_id"], "cantidad": det["cantidad"],
                "precio_unitario": det.get("precio_unitario",0), "subtotal": det.get("subtotal",0)
            })
        db.session.commit()
        return jsonify({"ok": True, "id": nid}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/ventas", methods=["POST"])
def crear_venta():
    if not _verifica_token():
        return jsonify({"error": "Token invalido"}), 401
    data = request.get_json(silent=True) or {}
    try:
        if not data.get("producto_id") or not data.get("vendedor_id"):
            return jsonify({"error": "producto_id y vendedor_id requeridos"}), 400
        res = db.session.execute(text("""
            INSERT INTO comercial_ventas (producto_id, fecha_venta, cantidad, vendedor_id, cliente_id, tipo_comprobante, numero_comprobante)
            VALUES (:producto_id, NOW(), :cantidad, :vendedor_id, :cliente_id, :tipo_comprobante, :numero_comprobante)
        """), {
            "producto_id": data["producto_id"], "cantidad": data.get("cantidad",1),
            "vendedor_id": data["vendedor_id"], "cliente_id": data.get("cliente_id"),
            "tipo_comprobante": data.get("tipo_comprobante","boleta"), "numero_comprobante": data.get("numero_comprobante")
        })
        # Antes del commit (misma transaccion/conexion): LAST_INSERT_ID() es por-conexion.
        nid = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        db.session.commit()
        return jsonify({"ok": True, "id": nid}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


def _aplicar_evento(tipo, datos):
    """Aplica un evento recibido del agente de mensajes (RabbitMQ).

    - producto.actualizado: actualiza la copia local del producto.
    - cliente.registrado: actualiza la copia local del cliente.
    - pedido.creado / venta.registrada: deja registro en el servicio.
    """
    try:
        if tipo == "producto.actualizado":
            db.session.execute(text("""
                UPDATE productos SET nombre = COALESCE(:nombre, nombre),
                                    precio = COALESCE(:precio, precio)
                WHERE id = :id
            """), {"nombre": datos.get("nombre"), "precio": datos.get("precio"),
                   "id": datos.get("id")})
            db.session.commit()
            return True
        if tipo == "cliente.registrado":
            # Copia local del cliente (si la tabla aun no existe en este
            # servicio, el evento se responde OK para no re-encolarlo).
            try:
                db.session.execute(text("""
                    INSERT INTO clientes (nombres, apellidos, correo, telefono, estado)
                    VALUES (:n, :a, :c, :t, 1)
                    ON DUPLICATE KEY UPDATE
                        nombres = VALUES(nombres), apellidos = VALUES(apellidos),
                        telefono = VALUES(telefono)
                """), {
                    "n": datos.get("nombres"), "a": datos.get("apellidos"),
                    "c": datos.get("email"), "t": datos.get("telefono"),
                })
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"[ventas] sin copia local de clientes ({str(e)[:90]})")
            return True
        if tipo in ("pedido.creado", "venta.registrada"):
            print(f"[ventas] evento '{tipo}' recibido "
                  f"(pedido {datos.get('pedido_id')}, total {datos.get('total')})")
            return True
        return True
    except Exception as e:
        db.session.rollback()
        print(f"[ventas] error aplicando el evento '{tipo}': {e}")
        return False


if __name__ == "__main__":
    try:
        from rabbit_consumidor import iniciar_consumidor
        iniciar_consumidor("ventas", _aplicar_evento)
    except Exception as e:
        print(f"[ventas] no se pudo iniciar el consumidor de eventos: {e}")
    app.run(host="127.0.0.1", port=8002)
