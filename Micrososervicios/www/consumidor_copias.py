"""Consumidor de eventos del agente de mensajes en el gateway.

En alwaysdata el gateway corre en un solo proceso uWSGI, asi que es el
propio gateway quien consume los eventos de las colas y mantiene al dia las
copias locales que cada microservicio necesita para sus JOIN.

Flujo:
    gateway publica evento -> cola del servicio -> este consumidor lo aplica
    -> solo las tablas que toca el evento se refrescan (consultas dirigidas).

La sincronizacion completa (sincronizar_copias.sql) sigue siendo la red de
seguridad: se ejecuta si un evento no se puede resolver, si una consulta
falla y, ademas, periodicamente cada SINCRONIZACION_COMPLETA_CADA segundos.
"""
import os
import threading
import time
from pathlib import Path

from sqlalchemy import text

_candado = threading.Lock()
_hay_pendientes = threading.Event()
_ultima_aplicacion = 0.0
_vistos = {}
SERVICIOS = ("inventario", "ventas", "usuarios", "clientes")
SINCRONIZACION_COMPLETA_CADA = 600   # red de seguridad periodica (10 min)
VENTANA_DEDUP = 5.0                  # mismo evento repetido en la ventana
# El script de sincronizacion de copias puede estar en la raiz del proyecto
# o junto a la app (www/).
RUTAS_SQL = (
    Path(__file__).resolve().parent.parent / "sincronizar_copias.sql",
    Path(__file__).resolve().parent / "sincronizar_copias.sql",
)

# Columnas de cada copia (las mismas de sincronizar_copias.sql; un test las
# contrasta con el script para que no se desincronicen).
COLUMNAS_PRODUCTOS = ("id", "nombre", "descripcion", "cantidad", "proveedor_id",
                      "precio", "imagen", "id_categoria", "precio_oferta",
                      "destacado", "codigo_barras", "estado", "stock_minimo",
                      "stock_maximo", "costo")
COLUMNAS_VENTAS = ("id", "producto_id", "fecha_venta", "cantidad", "vendedor_id",
                   "cliente_id", "tipo_comprobante", "numero_comprobante", "estado",
                   "cliente_nombres", "cliente_apellidos", "cliente_documento",
                   "cliente_email", "cliente_direccion", "cliente_direccion_fiscal",
                   "cliente_razon_social", "pedido_id", "metodo_pago",
                   "monto_recibido", "vuelto", "cliente_tipo_documento",
                   "cliente_telefono")
COLUMNAS_CLIENTES = ("id", "dni", "nombres", "apellidos", "correo", "telefono",
                     "direccion", "clave", "fecha_registro", "estado", "ruc",
                     "departamento", "provincia", "distrito",
                     "token_recuperacion", "token_expiracion", "puntos", "ce",
                     "referencia")


def _ruta_sql():
    for ruta in RUTAS_SQL:
        if ruta.is_file():
            return ruta
    return None


def _sentencias():
    """Divide el script de sincronizacion en sentencias (sin comentarios)."""
    ruta = _ruta_sql()
    if not ruta:
        return []
    sql = ruta.read_text(encoding="utf-8", errors="replace")
    salida = []
    for bloque in sql.split(";\n"):
        limpio = "\n".join(l for l in bloque.split("\n")
                           if l.strip() and not l.strip().startswith("--")).strip()
        if limpio:
            salida.append(limpio)
    return salida


def aplicar_copias():
    """Ejecuta la sincronizacion completa de copias locales (mismo SQL del cron)."""
    global _ultima_aplicacion
    with _candado:
        _ultima_aplicacion = time.time()
        try:
            from app import app, db
            sentencias = _sentencias()
            if not sentencias:
                print("[consumidor] no se encontro sincronizar_copias.sql")
                return False
            with app.app_context():
                for stmt in sentencias:
                    try:
                        db.session.execute(text(stmt))
                    except Exception as e:
                        db.session.rollback()
                        print(f"[consumidor] error al aplicar una sentencia: {str(e)[:120]}")
                        return False
                db.session.commit()
            print("[consumidor] copias locales sincronizadas")
            return True
        except Exception as e:
            print(f"[consumidor] error aplicando copias: {e}")
            return False


# ------------------------------------------------------------------
# Consultas dirigidas: solo las tablas que toca el evento
# ------------------------------------------------------------------
def _bd(variable, por_defecto):
    return (os.environ.get(variable) or por_defecto).strip() or por_defecto


def _nombres_bd():
    """Nombres de las bases (se leen en cada llamada: el .env se carga al importar la app)."""
    return {
        "inventario": _bd("MS_INVENTARIO_DB", "librospe_ms_inventario"),
        "ventas": _bd("MS_VENTAS_DB", "librospe_ms_ventas"),
        "usuarios": _bd("MS_USUARIOS_DB", "librospe_ms_usuarios"),
        "clientes": _bd("MS_CLIENTES_DB", "librospe_ms_clientes"),
    }


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _copia(bd_origen, bd_destino, tabla, columnas, donde, donde_s):
    """(INSERT IGNORE ... SELECT ... WHERE `donde`) + (UPDATE con JOIN ... WHERE `donde_s`)."""
    columnas_sql = ", ".join(f"`{c}`" for c in columnas)
    asigna = ", ".join(f"d.`{c}` = s.`{c}`" for c in columnas if c != "id")
    return [
        f"INSERT IGNORE INTO `{bd_destino}`.`{tabla}` ({columnas_sql}) "
        f"SELECT {columnas_sql} FROM `{bd_origen}`.`{tabla}` WHERE {donde}",
        f"UPDATE `{bd_destino}`.`{tabla}` d JOIN `{bd_origen}`.`{tabla}` s "
        f"ON d.`id` = s.`id` SET {asigna} WHERE {donde_s}",
    ]


def _con_params(sentencias, params):
    return [(sql, dict(params)) for sql in sentencias]


def _sentencias_dirigidas(tipo, datos):
    """Sentencias minimas para aplicar un evento concreto.

    Devuelve [(sql, params), ...] o None si el evento no se puede resolver
    de forma dirigida (entonces el hilo aplicador hace la sincronizacion
    completa, que ademas cubre el resto de las copias).
    """
    if not isinstance(datos, dict):
        return None
    bd = _nombres_bd()
    copia_producto = ("productos", COLUMNAS_PRODUCTOS)

    if tipo in ("producto.actualizado", "producto.alerta_stock"):
        pid = _entero(datos.get("id") or datos.get("producto_id"))
        if pid is None:
            return None
        return _con_params(_copia(bd["inventario"], bd["ventas"], *copia_producto,
                                  "`id` = :pid", "s.`id` = :pid"), {"pid": pid})

    if tipo == "venta.registrada":
        vid = _entero(datos.get("venta_id"))
        if vid is None:
            return None
        frases = _con_params(_copia(bd["ventas"], bd["inventario"], "ventas", COLUMNAS_VENTAS,
                                    "`id` = :vid", "s.`id` = :vid"), {"vid": vid})
        pid = _entero(datos.get("producto_id"))
        if pid is not None:
            # la venta desconto stock en inventario: la copia de ventas queda vieja
            frases += _con_params(_copia(bd["inventario"], bd["ventas"], *copia_producto,
                                         "`id` = :pid", "s.`id` = :pid"), {"pid": pid})
        return frases

    if tipo == "cliente.registrado":
        correo = str(datos.get("email") or datos.get("correo") or "").strip()
        if not correo:
            return None
        return _con_params(_copia(bd["clientes"], bd["ventas"], "clientes", COLUMNAS_CLIENTES,
                                  "`correo` = :correo", "s.`correo` = :correo"),
                           {"correo": correo})

    if tipo == "pedido.creado":
        pedido = _entero(datos.get("pedido_id"))
        pids = []
        for item in datos.get("items") or []:
            if isinstance(item, dict):
                pid = _entero(item.get("id"))
                if pid is not None:
                    pids.append(pid)
        frases = []
        if pedido is not None:
            # el pedido creo sus filas en ventas.ventas: copiarlas a inventario.ventas
            frases += _con_params(_copia(bd["ventas"], bd["inventario"], "ventas", COLUMNAS_VENTAS,
                                         "`pedido_id` = :pedido", "s.`pedido_id` = :pedido"),
                                  {"pedido": pedido})
        if pids:
            # el pedido desconto stock en inventario: refrescar la copia de ventas
            marcas = ", ".join(f":p{i}" for i in range(len(pids)))
            params = {f"p{i}": v for i, v in enumerate(pids)}
            frases += _con_params(_copia(bd["inventario"], bd["ventas"], *copia_producto,
                                         f"`id` IN ({marcas})", f"s.`id` IN ({marcas})"),
                                  params)
        return frases or None

    return None


# ------------------------------------------------------------------
# Consumo de eventos
# ------------------------------------------------------------------
def _clave_evento(tipo, datos):
    ident = (datos.get("venta_id") or datos.get("pedido_id") or datos.get("id")
             or datos.get("email") or datos.get("correo") or "")
    return f"{tipo}:{ident}"


def _recien_visto(clave):
    """True si el mismo evento llego hace menos de VENTANA_DEDUP segundos."""
    global _vistos
    ahora = time.time()
    visto = _vistos.get(clave)
    if visto is not None and ahora - visto < VENTANA_DEDUP:
        return True
    _vistos[clave] = ahora
    if len(_vistos) > 300:
        _vistos = {k: t for k, t in _vistos.items() if ahora - t < VENTANA_DEDUP}
    return False


def _handler(tipo, datos):
    """Aplica un evento sobre las copias con consultas dirigidas.

    Nunca lanza excepciones (mensajeria reencolaria el evento): si algo
    falla se pide la sincronizacion completa y se devuelve True.
    """
    try:
        if _recien_visto(_clave_evento(tipo, datos)):
            return True
        sentencias = _sentencias_dirigidas(tipo, datos)
    except Exception as e:
        print(f"[consumidor] evento '{tipo}' ilegible: {str(e)[:160]}")
        sentencias = None
    if not sentencias:
        _hay_pendientes.set()
        return True
    with _candado:
        try:
            from app import app, db
            with app.app_context():
                try:
                    for sql, params in sentencias:
                        db.session.execute(text(sql), params)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    raise
        except Exception as e:
            print(f"[consumidor] no se pudo aplicar '{tipo}': {str(e)[:160]}")
            _hay_pendientes.set()
    return True


def _hilo_aplicador():
    """Sincronizacion completa: bajo demanda (fallback) y periodica (cada 10 min)."""
    while True:
        espera = max(1.0, SINCRONIZACION_COMPLETA_CADA - (time.time() - _ultima_aplicacion))
        desperto = _hay_pendientes.wait(timeout=espera)
        _hay_pendientes.clear()
        if desperto or time.time() - _ultima_aplicacion >= SINCRONIZACION_COMPLETA_CADA:
            aplicar_copias()


def iniciar_consumidor_copias():
    """Arranca los consumidores de las colas del agente de mensajes."""
    if not os.environ.get("AMQP_URL", "").strip():
        print("[consumidor] sin AMQP_URL: no se arrancan los consumidores")
        return False
    from mensajeria import consumir_eventos
    threading.Thread(target=_hilo_aplicador, name="consumidor-copias", daemon=True).start()
    for servicio in SERVICIOS:
        threading.Thread(target=consumir_eventos, args=(servicio, _handler),
                         name=f"consumidor-{servicio}", daemon=True).start()
    print("[consumidor] consumidores de eventos arrancados:", ", ".join(SERVICIOS))
    return True
