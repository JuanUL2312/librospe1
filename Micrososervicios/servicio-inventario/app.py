"""Servicio INVENTARIO (puerto 8001). BD propia: librospe_ms_inventario.

Tablas: inventario_productos, inventario_categorias, inventario_proveedores.
Se comunica con otros servicios SOLO por HTTP + X-Service-Token.
"""
import hmac
import os
import re
import sys
from functools import wraps
from pathlib import Path
from urllib.parse import quote_plus

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def cargar_entorno():
    bases = [Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent, Path.home()]
    vistos = set()
    for base in bases:
        f = base / ".env"
        try:
            r = f.resolve()
        except OSError:
            continue
        if r in vistos or not f.is_file():
            continue
        vistos.add(r)
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
        # Antes del commit (misma transaccion/conexion): LAST_INSERT_ID() es por-conexion.
        nid = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        db.session.commit()
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
        # Antes del commit (misma transaccion/conexion): LAST_INSERT_ID() es por-conexion.
        nid = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        db.session.commit()
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
@servicio_requerido
def actualizar_stock(pid):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get("cantidad") is None:
        return jsonify({"error": "Cantidad requerida"}), 400
    cantidad_original = data["cantidad"]
    if isinstance(cantidad_original, bool):
        return jsonify({"error": "Cantidad debe ser un entero no negativo"}), 400
    try:
        cantidad = int(cantidad_original)
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Cantidad debe ser un entero no negativo"}), 400
    if cantidad < 0 or (isinstance(cantidad_original, float) and not cantidad_original.is_integer()):
        return jsonify({"error": "Cantidad debe ser un entero no negativo"}), 400
    try:
        res = db.session.execute(
            text("UPDATE inventario_productos SET cantidad=:c WHERE id=:id"),
            {"c": cantidad, "id": pid})
        if res.rowcount == 0:
            db.session.rollback()
            return jsonify({"error": "No encontrado"}), 404
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        app.logger.exception("Error actualizando stock del producto %s", pid)
        return jsonify({"error": "No se pudo actualizar el stock"}), 500


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


# ---------------------------------------------------------------------------
# Reserva atomica e idempotente de stock (usada por el checkout del gateway)
# ---------------------------------------------------------------------------
TABLA_STOCK = "inventario_productos"
TABLA_RESERVAS = "reservas_stock"
_REFERENCIA_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,63}$")
_tabla_reservas_lista = False

DDL_RESERVAS = f"""
CREATE TABLE IF NOT EXISTS {TABLA_RESERVAS} (
    id BIGINT NOT NULL AUTO_INCREMENT,
    referencia VARCHAR(64) NOT NULL,
    producto_id INT NOT NULL,
    cantidad INT NOT NULL,
    estado VARCHAR(16) NOT NULL DEFAULT 'reservado',
    documento_tipo VARCHAR(16) NULL,
    documento_id INT NULL,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_reserva_producto (referencia, producto_id),
    KEY idx_reserva_estado (estado),
    KEY idx_reserva_documento (documento_tipo, documento_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def _asegurar_tabla_reservas():
    """Crea la tabla de idempotencia si aun no existe (idempotente)."""
    global _tabla_reservas_lista
    if _tabla_reservas_lista:
        return
    try:
        motor = db.engine
    except Exception:
        motor = db.get_engine()
    with motor.begin() as con:
        con.execute(text(DDL_RESERVAS))
    _tabla_reservas_lista = True


def _normalizar_referencia(valor):
    referencia = str(valor or "").strip()
    if not _REFERENCIA_RE.match(referencia):
        raise ValueError("clave de idempotencia invalida")
    return referencia


def _normalizar_items(items):
    if not isinstance(items, (list, tuple)) or not items:
        raise ValueError("no hay productos que reservar")
    if len(items) > 100:
        raise ValueError("demasiados productos en el pedido")
    agrupados = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("producto invalido")
        crudo_id = item.get("id")
        crudo_cantidad = item.get("cantidad")
        if isinstance(crudo_id, bool) or isinstance(crudo_cantidad, bool):
            raise ValueError("producto o cantidad invalidos")
        try:
            producto_id = int(crudo_id)
            cantidad = int(crudo_cantidad)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("producto o cantidad invalidos") from None
        if isinstance(crudo_cantidad, float) and not crudo_cantidad.is_integer():
            raise ValueError("la cantidad debe ser un entero positivo")
        if producto_id <= 0 or cantidad <= 0 or cantidad > 1_000_000:
            raise ValueError("la cantidad debe ser un entero positivo")
        agrupados[producto_id] = agrupados.get(producto_id, 0) + cantidad
        if agrupados[producto_id] > 1_000_000:
            raise ValueError("cantidad total fuera de rango")
    return [{"id": pid, "cantidad": cant} for pid, cant in agrupados.items()]


def _leer_reserva(referencia):
    return db.session.execute(
        text(
            f"SELECT referencia, producto_id, cantidad, estado, documento_tipo, "
            f"documento_id FROM {TABLA_RESERVAS} WHERE referencia=:r ORDER BY id"
        ),
        {"r": referencia},
    ).mappings().all()


def _respuesta_reserva(filas, items):
    """Respuesta idempotente, sin aceptar que se reutilice la clave con otro carrito."""
    esperado = {item["id"]: item["cantidad"] for item in items}
    registrado = {int(f["producto_id"]): int(f["cantidad"]) for f in filas}
    if registrado != esperado:
        return jsonify({
            "ok": False, "duplicado": True,
            "codigo": "clave_idempotencia_reutilizada",
            "error": "La clave ya fue usada para un pedido diferente.",
        }), 409
    estados = {f["estado"] for f in filas}
    documento_id = next((f["documento_id"] for f in filas
                         if f["documento_id"] is not None), None)
    documento_tipo = next((f["documento_tipo"] for f in filas
                           if f["documento_tipo"]), None)
    if "liberado" in estados:
        return jsonify({
            "ok": False, "duplicado": True, "estado": "liberado",
            "codigo": "reserva_liberada",
            "error": "La reserva de este pedido fue cancelada. Vuelve a intentarlo.",
        }), 409
    estado = "confirmado" if estados == {"confirmado"} else "reservado"
    return jsonify({
        "ok": True, "duplicado": True, "estado": estado,
        "documento_tipo": documento_tipo, "documento_id": documento_id,
        "referencia": filas[0]["referencia"],
    }), 200


@app.route("/_reservar-stock", methods=["POST"])
@servicio_requerido
def reservar_stock():
    """Descuenta stock una sola vez por referencia (idempotente y atomico)."""
    data = request.get_json(silent=True) or {}
    try:
        referencia = _normalizar_referencia(data.get("referencia"))
        items = _normalizar_items(data.get("items"))
    except ValueError as e:
        return jsonify({"ok": False, "codigo": "datos_invalidos",
                        "error": str(e)}), 400
    documento_tipo = str(data.get("documento_tipo") or "pedido")[:16]
    try:
        _asegurar_tabla_reservas()
        previas = _leer_reserva(referencia)
        if previas:
            db.session.rollback()
            return _respuesta_reserva(previas, items)
        for item in items:
            db.session.execute(
                text(
                    f"INSERT INTO {TABLA_RESERVAS} "
                    "(referencia, producto_id, cantidad, estado) "
                    "VALUES (:r, :p, :c, 'reservado')"
                ),
                {"r": referencia, "p": item["id"], "c": item["cantidad"]},
            )
            res = db.session.execute(
                text(
                    f"UPDATE {TABLA_STOCK} SET cantidad = cantidad - :c "
                    "WHERE id = :p AND cantidad >= :c"
                ),
                {"c": item["cantidad"], "p": item["id"]},
            )
            if res.rowcount != 1:
                db.session.rollback()
                return jsonify({
                    "ok": False, "codigo": "stock_insuficiente",
                    "error": "Stock insuficiente para completar el pedido.",
                    "producto_id": item["id"],
                }), 409
        db.session.commit()
        return jsonify({
            "ok": True, "duplicado": False, "estado": "reservado",
            "referencia": referencia, "documento_tipo": documento_tipo,
        }), 200
    except IntegrityError:
        # Dos peticiones identicas simultaneas: el indice unico decide.
        db.session.rollback()
        previas = _leer_reserva(referencia)
        if previas:
            return _respuesta_reserva(previas, items)
        return jsonify({"ok": False, "codigo": "reserva_en_conflicto",
                        "error": "No se pudo registrar la reserva."}), 409
    except Exception:
        db.session.rollback()
        app.logger.exception("Error reservando stock para %s", referencia)
        return jsonify({"ok": False, "codigo": "inventario_no_disponible",
                        "error": "No se pudo reservar el stock."}), 503


@app.route("/_liberar-stock", methods=["POST"])
@servicio_requerido
def liberar_stock():
    """Devuelve el stock de una reserva no confirmada (compensacion)."""
    data = request.get_json(silent=True) or {}
    try:
        referencia = _normalizar_referencia(data.get("referencia"))
    except ValueError as e:
        return jsonify({"ok": False, "codigo": "datos_invalidos",
                        "error": str(e)}), 400
    try:
        _asegurar_tabla_reservas()
        filas = db.session.execute(
            text(
                f"SELECT producto_id, cantidad, estado FROM {TABLA_RESERVAS} "
                "WHERE referencia=:r FOR UPDATE"
            ),
            {"r": referencia},
        ).mappings().all()
        reservadas = [f for f in filas if f["estado"] == "reservado"]
        for fila in reservadas:
            db.session.execute(
                text(f"UPDATE {TABLA_STOCK} SET cantidad = cantidad + :c "
                     "WHERE id = :p"),
                {"c": fila["cantidad"], "p": fila["producto_id"]},
            )
        if reservadas:
            db.session.execute(
                text(f"UPDATE {TABLA_RESERVAS} SET estado='liberado' "
                     "WHERE referencia=:r AND estado='reservado'"),
                {"r": referencia},
            )
        db.session.commit()
        return jsonify({"ok": True, "liberadas": len(reservadas),
                        "referencia": referencia}), 200
    except Exception:
        db.session.rollback()
        app.logger.exception("Error liberando la reserva %s", referencia)
        return jsonify({"ok": False, "codigo": "inventario_no_disponible",
                        "error": "No se pudo liberar la reserva."}), 503


@app.route("/_confirmar-stock", methods=["POST"])
@servicio_requerido
def confirmar_stock():
    """Vincula la reserva con el pedido/venta ya guardado (idempotente)."""
    data = request.get_json(silent=True) or {}
    try:
        referencia = _normalizar_referencia(data.get("referencia"))
        documento_id = int(data.get("documento_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "codigo": "datos_invalidos",
                        "error": "referencia o documento_id invalidos"}), 400
    documento_tipo = str(data.get("documento_tipo") or "pedido")[:16]
    try:
        _asegurar_tabla_reservas()
        res = db.session.execute(
            text(
                f"UPDATE {TABLA_RESERVAS} SET estado='confirmado', "
                "documento_tipo=:t, documento_id=:d "
                "WHERE referencia=:r AND estado='reservado'"
            ),
            {"r": referencia, "t": documento_tipo, "d": documento_id},
        )
        db.session.commit()
        if res.rowcount:
            return jsonify({"ok": True, "documento_id": documento_id}), 200
        filas = _leer_reserva(referencia)
        if filas and all(f["estado"] == "confirmado" for f in filas):
            return jsonify({"ok": True, "duplicado": True,
                            "documento_id": documento_id}), 200
        if filas and any(f["estado"] == "liberado" for f in filas):
            return jsonify({"ok": False, "codigo": "reserva_liberada",
                            "error": "La reserva fue liberada."}), 409
        return jsonify({"ok": False, "codigo": "reserva_no_encontrada",
                        "error": "No hay una reserva activa para confirmar."}), 404
    except Exception:
        db.session.rollback()
        app.logger.exception("Error confirmando la reserva %s", referencia)
        return jsonify({"ok": False, "codigo": "inventario_no_disponible",
                        "error": "No se pudo confirmar la reserva."}), 503


def _aplicar_evento(tipo, datos):
    """Aplica un evento recibido del agente de mensajes (RabbitMQ).

    - pedido.creado / venta.registrada: informativos; el Gateway ya descuenta
      stock antes de confirmar el pedido/venta.
    - producto.actualizado: actualiza precio y stock minimo.
    Devuelve True si el evento quedo aplicado (no se re-encola).
    """
    try:
        if tipo in ("pedido.creado", "venta.registrada"):
            # Eventos de sincronizacion: el Gateway ya realizo el descuento
            # atomico; repetir el evento no modifica el inventario.
            return True
        if tipo == "producto.actualizado":
            db.session.execute(text("""
                UPDATE inventario_productos
                SET precio = COALESCE(:precio, precio),
                    cantidad = COALESCE(:cantidad, cantidad),
                    stock_minimo = COALESCE(:smin, stock_minimo)
                WHERE id = :id
            """), {
                "precio": datos.get("precio"),
                "cantidad": datos.get("cantidad"),
                "smin": datos.get("stock_minimo"),
                "id": datos.get("id"),
            })
            db.session.commit()
            print(f"[inventario] producto {datos.get('id')} actualizado por evento")
            return True
        if tipo == "producto.alerta_stock":
            print(f"[inventario] alerta de stock: {datos.get('nombre')} "
                  f"({datos.get('cantidad')}/{datos.get('stock_minimo')})")
            return True
        # Evento que no aplica a este servicio: se responde OK para no re-encolar.
        return True
    except Exception as e:
        db.session.rollback()
        print(f"[inventario] error aplicando el evento '{tipo}': {e}")
        return False


def _arrancar_consumidor():
    if "pytest" in sys.modules:
        return
    if os.environ.get("MS_CONSUMIDOR", "1").lower() in ("0", "false", "no"):
        return
    try:
        from rabbit_consumidor import iniciar_consumidor
        iniciar_consumidor("inventario", _aplicar_evento)
    except Exception as e:
        print(f"[inventario] no se pudo iniciar el consumidor de eventos: {e}")


_arrancar_consumidor()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8001, threaded=True)
