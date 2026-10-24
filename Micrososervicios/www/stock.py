"""Reserva de stock del checkout (patron saga).

El microservicio de inventario es el dueno del stock. El gateway le pide una
reserva antes de confirmar un pedido; la reserva:

- descuenta con ``UPDATE ... WHERE cantidad >= :cantidad`` (nunca deja stock
  negativo y serializa pedidos concurrentes en la fila del producto),
- se registra en ``reservas_stock`` con una clave de idempotencia
  (``referencia``) unica por producto, de modo que repetir la peticion no
  vuelve a descontar,
- se puede liberar (compensacion) si el pedido no llega a guardarse, y
- se confirma con el id del pedido cuando la transaccion del pedido termina.

Si el microservicio no responde, el gateway falla cerrado. El acceso directo
a la BD solo se conserva como compatibilidad transitoria y requiere habilitar
expl?citamente ``INVENTARIO_DB_FALLBACK`` en la configuraci?n de la app.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TABLA_RESERVAS = "reservas_stock"
TABLA_PRODUCTOS = "inventario_productos"
MAX_ITEMS = 100
MAX_CANTIDAD = 1_000_000
TIMEOUT_HTTP = 3.0

_REFERENCIA_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,63}$")
_tabla_lista = False

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


class StockError(ValueError):
    """Datos de reserva invalidos (referencia o items)."""


class _StockInsuficiente(Exception):
    def __init__(self, producto_id, disponible=None):
        super().__init__(f"stock insuficiente para el producto {producto_id}")
        self.producto_id = producto_id
        self.disponible = disponible


def nueva_referencia() -> str:
    """Clave de idempotencia para peticiones que no la envian."""
    return uuid.uuid4().hex


def normalizar_referencia(valor) -> str:
    """Valida la clave de idempotencia (8-64 caracteres seguros)."""
    referencia = str(valor or "").strip()
    if not _REFERENCIA_RE.match(referencia):
        raise StockError("clave de idempotencia invalida")
    return referencia


def normalizar_items(items) -> list[dict]:
    """Valida y agrupa los items por producto.

    Agrupar es importante: dos lineas del carrito con el mismo producto deben
    descontar la suma, no competir por la misma fila.
    """
    if not isinstance(items, (list, tuple)) or not items:
        raise StockError("no hay productos que reservar")
    if len(items) > MAX_ITEMS:
        raise StockError("demasiados productos en el pedido")

    agrupados: dict[int, int] = {}
    for item in items:
        if not isinstance(item, dict):
            raise StockError("producto invalido")
        crudo_id = item.get("id")
        crudo_cantidad = item.get("cantidad")
        if isinstance(crudo_id, bool) or isinstance(crudo_cantidad, bool):
            raise StockError("producto o cantidad invalidos")
        try:
            producto_id = int(crudo_id)
            cantidad = int(crudo_cantidad)
        except (TypeError, ValueError, OverflowError):
            raise StockError("producto o cantidad invalidos") from None
        if (isinstance(crudo_cantidad, float) and not crudo_cantidad.is_integer()):
            raise StockError("la cantidad debe ser un entero positivo")
        if producto_id <= 0 or cantidad <= 0 or cantidad > MAX_CANTIDAD:
            raise StockError("la cantidad debe ser un entero positivo")
        agrupados[producto_id] = agrupados.get(producto_id, 0) + cantidad
        if agrupados[producto_id] > MAX_CANTIDAD:
            raise StockError("cantidad total fuera de rango")
    return [{"id": pid, "cantidad": cant} for pid, cant in agrupados.items()]


def _url_inventario() -> str:
    valor = ""
    try:
        from flask import current_app

        valor = current_app.config.get("MS_INVENTARIO_URL", "")
    except RuntimeError:
        pass
    valor = valor or os.environ.get("MS_INVENTARIO_URL", "http://127.0.0.1:8001")
    return str(valor).rstrip("/")


def _permitir_respaldo_bd() -> bool:
    """El acceso Gateway->BD queda desactivado salvo opt-in de migracion."""
    try:
        from flask import current_app
        return bool(current_app.config.get("INVENTARIO_DB_FALLBACK", False))
    except RuntimeError:
        return os.environ.get("INVENTARIO_DB_FALLBACK", "false").lower() in (
            "1", "true", "yes")


def _token_servicio() -> str:
    valor = ""
    try:
        from flask import current_app

        valor = current_app.config.get("SERVICE_TOKEN", "")
    except RuntimeError:
        pass
    return valor or os.environ.get("SERVICE_TOKEN", "")


def _post(ruta: str, payload: dict, timeout: float = TIMEOUT_HTTP):
    """POST al microservicio. Devuelve (status, cuerpo).

    ``status`` es None cuando no hubo respuesta (servicio caido/timeout), lo
    que permite al llamador decidir si usa el respaldo directo.
    """
    url = _url_inventario() + ruta
    datos = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    cabeceras = {
        "Content-Type": "application/json",
        "X-Service-Token": _token_servicio(),
    }
    req = Request(url, data=datos, headers=cabeceras, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            cuerpo = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(cuerpo)
    except HTTPError as e:
        try:
            cuerpo = json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            cuerpo = {"error": f"inventario respondio HTTP {e.code}"}
        return e.code, cuerpo
    except (URLError, TimeoutError, OSError, ValueError) as e:
        return None, {"error": f"inventario no disponible: {str(e)[:160]}"}


def _motor_inventario():
    """Engine del bind de inventario (requiere contexto de aplicacion)."""
    from app import db

    try:
        motor = db.get_engine(bind="inventario")
    except Exception:
        motor = None
    if motor is None and hasattr(db, "engines"):
        motor = db.engines.get("inventario")
    if motor is None:
        raise RuntimeError("bind de inventario no disponible")
    return motor


def _asegurar_tabla(motor) -> None:
    global _tabla_lista
    if _tabla_lista:
        return
    from sqlalchemy import text

    with motor.begin() as con:
        con.execute(text(DDL_RESERVAS))
    _tabla_lista = True


def _resultado_duplicado(filas, items=None) -> dict:
    if items is not None:
        esperado = {item["id"]: item["cantidad"] for item in items}
        registrado = {int(f["producto_id"]): int(f["cantidad"]) for f in filas}
        if registrado != esperado:
            return {
                "ok": False, "duplicado": True,
                "codigo": "clave_idempotencia_reutilizada",
                "error": "La clave ya fue usada para un pedido diferente.",
            }
    estados = {f["estado"] for f in filas}
    documento_id = next((f["documento_id"] for f in filas
                         if f["documento_id"] is not None), None)
    documento_tipo = next((f["documento_tipo"] for f in filas
                           if f["documento_tipo"]), None)
    if "liberado" in estados:
        return {
            "ok": False,
            "codigo": "reserva_liberada",
            "error": "La reserva de este pedido fue cancelada. Vuelve a intentarlo.",
            "duplicado": True,
            "estado": "liberado",
            "documento_id": documento_id,
        }
    estado = "confirmado" if estados == {"confirmado"} else "reservado"
    return {
        "ok": True,
        "duplicado": True,
        "estado": estado,
        "documento_tipo": documento_tipo,
        "documento_id": documento_id,
        "referencia": filas[0]["referencia"],
    }


def _leer_reserva(con, referencia):
    from sqlalchemy import text

    return con.execute(
        text(
            f"SELECT referencia, producto_id, cantidad, estado, documento_tipo, "
            f"documento_id FROM {TABLA_RESERVAS} WHERE referencia=:r ORDER BY id"
        ),
        {"r": referencia},
    ).mappings().all()


def _reservar_directo(referencia: str, items: list[dict]) -> dict:
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    for intento in range(2):
        try:
            motor = _motor_inventario()
            _asegurar_tabla(motor)
            with motor.begin() as con:
                previas = _leer_reserva(con, referencia)
                if previas:
                    return _resultado_duplicado(previas, items)
                for item in items:
                    con.execute(
                        text(
                            f"INSERT INTO {TABLA_RESERVAS} "
                            "(referencia, producto_id, cantidad, estado) "
                            "VALUES (:r, :p, :c, 'reservado')"
                        ),
                        {"r": referencia, "p": item["id"], "c": item["cantidad"]},
                    )
                    res = con.execute(
                        text(
                            f"UPDATE {TABLA_PRODUCTOS} "
                            "SET cantidad = cantidad - :c "
                            "WHERE id = :p AND cantidad >= :c"
                        ),
                        {"c": item["cantidad"], "p": item["id"]},
                    )
                    if res.rowcount != 1:
                        raise _StockInsuficiente(item["id"])
            return {
                "ok": True,
                "duplicado": False,
                "estado": "reservado",
                "referencia": referencia,
            }
        except IntegrityError:
            # Otra peticion con la misma referencia gano la carrera del
            # indice unico: se relee para devolver el mismo resultado.
            if intento == 0:
                continue
            return {
                "ok": False,
                "codigo": "reserva_en_conflicto",
                "error": "No se pudo registrar la reserva. Intenta de nuevo.",
            }
        except _StockInsuficiente as e:
            return {
                "ok": False,
                "codigo": "stock_insuficiente",
                "error": "Stock insuficiente para completar el pedido.",
                "producto_id": e.producto_id,
            }
        except Exception as e:
            return {
                "ok": False,
                "codigo": "inventario_no_disponible",
                "error": "No se pudo reservar el stock. Intenta de nuevo.",
                "detalle": str(e)[:200],
            }
    return {
        "ok": False,
        "codigo": "reserva_en_conflicto",
        "error": "No se pudo registrar la reserva. Intenta de nuevo.",
    }


def reservar_stock(referencia, items, documento_tipo="pedido") -> dict:
    """Reserva ``items`` de forma atomica e idempotente.

    Devuelve un dict con ``ok``. Si ``ok`` es False, ``codigo`` indica el
    motivo (``stock_insuficiente``, ``inventario_no_disponible``, etc.).
    """
    referencia = normalizar_referencia(referencia)
    items = normalizar_items(items)
    estado, cuerpo = _post(
        "/_reservar-stock",
        {
            "referencia": referencia,
            "items": items,
            "documento_tipo": documento_tipo,
        },
    )
    if estado is not None:
        if estado == 200 and cuerpo.get("ok"):
            cuerpo.setdefault("estado", "reservado")
            cuerpo["via"] = "servicio"
            return cuerpo
        # 4xx: el servicio respondio y su decision es autoritativa. 5xx: se
        # intenta el respaldo directo porque puede ser un fallo transitorio.
        if estado < 500:
            cuerpo.setdefault("ok", False)
            cuerpo["via"] = "servicio"
            return cuerpo
    # El acceso directo solo puede habilitarse expresamente durante una
    # migracion. Por defecto se falla cerrado ante errores de comunicacion.
    if _permitir_respaldo_bd():
        resultado = _reservar_directo(referencia, items)
        resultado["via"] = "bd_compatibilidad"
        return resultado
    return {
        "ok": False,
        "codigo": "inventario_no_disponible",
        "error": "No se pudo confirmar la reserva con el servicio de inventario.",
    }


def liberar_stock(referencia) -> dict:
    """Libera (compensa) las reservas aun no confirmadas de una referencia."""
    referencia = normalizar_referencia(referencia)
    estado, cuerpo = _post("/_liberar-stock", {"referencia": referencia})
    if estado is not None:
        if estado < 500:
            cuerpo.setdefault("ok", estado == 200)
            cuerpo["via"] = "servicio"
            return cuerpo
    if _permitir_respaldo_bd():
        return _liberar_directo(referencia)
    return {
        "ok": False,
        "codigo": "inventario_no_disponible",
        "error": "No se pudo confirmar la compensacion con el servicio de inventario.",
    }


def _liberar_directo(referencia: str) -> dict:
    from sqlalchemy import text

    try:
        motor = _motor_inventario()
        _asegurar_tabla(motor)
        with motor.begin() as con:
            filas = con.execute(
                text(
                    f"SELECT producto_id, cantidad, estado FROM {TABLA_RESERVAS} "
                    "WHERE referencia=:r FOR UPDATE"
                ),
                {"r": referencia},
            ).mappings().all()
            reservadas = [f for f in filas if f["estado"] == "reservado"]
            for fila in reservadas:
                con.execute(
                    text(
                        f"UPDATE {TABLA_PRODUCTOS} "
                        "SET cantidad = cantidad + :c WHERE id = :p"
                    ),
                    {"c": fila["cantidad"], "p": fila["producto_id"]},
                )
            if reservadas:
                con.execute(
                    text(
                        f"UPDATE {TABLA_RESERVAS} SET estado='liberado' "
                        "WHERE referencia=:r AND estado='reservado'"
                    ),
                    {"r": referencia},
                )
        return {"ok": True, "via": "bd", "liberadas": len(reservadas)}
    except Exception as e:
        return {
            "ok": False,
            "codigo": "inventario_no_disponible",
            "error": "No se pudo liberar la reserva; requiere conciliacion.",
            "detalle": str(e)[:200],
        }


def confirmar_stock(referencia, documento_id, documento_tipo="pedido") -> dict:
    """Marca la reserva como confirmada y la vincula al documento creado."""
    referencia = normalizar_referencia(referencia)
    try:
        documento_id = int(documento_id)
    except (TypeError, ValueError):
        return {"ok": False, "codigo": "documento_invalido",
                "error": "documento_id invalido"}
    estado, cuerpo = _post(
        "/_confirmar-stock",
        {
            "referencia": referencia,
            "documento_tipo": documento_tipo,
            "documento_id": documento_id,
        },
    )
    if estado is not None:
        if estado < 500:
            cuerpo.setdefault("ok", estado == 200)
            cuerpo["via"] = "servicio"
            return cuerpo
    if _permitir_respaldo_bd():
        return _confirmar_directo(referencia, documento_id, documento_tipo)
    return {
        "ok": False,
        "codigo": "inventario_no_disponible",
        "error": "No se pudo confirmar la reserva con el servicio de inventario.",
    }


def _confirmar_directo(referencia: str, documento_id: int,
                       documento_tipo: str) -> dict:
    from sqlalchemy import text

    try:
        motor = _motor_inventario()
        _asegurar_tabla(motor)
        with motor.begin() as con:
            res = con.execute(
                text(
                    f"UPDATE {TABLA_RESERVAS} "
                    "SET estado='confirmado', documento_tipo=:t, documento_id=:d "
                    "WHERE referencia=:r AND estado='reservado'"
                ),
                {"r": referencia, "t": documento_tipo, "d": documento_id},
            )
            if res.rowcount:
                return {"ok": True, "via": "bd", "documento_id": documento_id}
            filas = _leer_reserva(con, referencia)
        if filas and all(f["estado"] == "confirmado" for f in filas):
            return {"ok": True, "via": "bd", "duplicado": True,
                    "documento_id": documento_id}
        return {
            "ok": False,
            "codigo": "reserva_no_encontrada",
            "error": "No hay una reserva activa para confirmar.",
        }
    except Exception as e:
        return {
            "ok": False,
            "codigo": "inventario_no_disponible",
            "error": "No se pudo confirmar la reserva.",
            "detalle": str(e)[:200],
        }
