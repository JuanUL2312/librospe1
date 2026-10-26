"""Agente de mensajes (RabbitMQ) para la arquitectura de microservicios.

El gateway publica los eventos del dominio en un exchange de RabbitMQ y cada
microservicio consume los que le interesan, en vez de copiar tablas por SQL.

    gateway  --publica-->  exchange "librospe.eventos"  --consume-->  servicios
                             (topic, durable)                    (colasbindings)

Si no hay broker configurado (AMQP_URL vacio) o no se puede alcanzar, los
eventos NO se pierden: se guardan en la tabla `eventos_pendientes` (outbox) y
el cron `procesar_eventos.sh` los reintenta. Asi el sistema sigue funcionando
igual que con la sincronizacion por SQL.

Nunca lanza excepciones: cualquier fallo se registra y se degrada al outbox.
"""
import json
import os
import threading
import time
from datetime import datetime
from sqlalchemy import text

# ------------------------------------------------------------------
# Configuracion
# ------------------------------------------------------------------
EXCHANGE = (os.environ.get("AMQP_EXCHANGE", "librospe.eventos") or "librospe.eventos").strip()
COLAS = {
    "inventario": os.environ.get("AMQP_COLA_INVENTARIO", "librospe.inventario"),
    "ventas": os.environ.get("AMQP_COLA_VENTAS", "librospe.ventas"),
    "usuarios": os.environ.get("AMQP_COLA_USUARIOS", "librospe.usuarios"),
    "clientes": os.environ.get("AMQP_COLA_CLIENTES", "librospe.clientes"),
}
# Eventos -> servicios que los consumen (solo los que se emiten realmente)
EVENTOS = {
    "pedido.creado": ["inventario", "ventas"],
    "venta.registrada": ["inventario", "ventas"],
    "producto.actualizado": ["ventas", "inventario"],
    "cliente.registrado": ["ventas", "usuarios"],
    "producto.alerta_stock": ["usuarios", "ventas"],
}

_estado = {"broker": False, "broker_configurado": False,
           "ultimo_error": "", "publicados": 0, "en_outbox": 0,
           "ultimo_evento": None, "ultimo_intento": None}
_ultimo_ping_broker = 0.0
_CACHE_PING_S = 20.0
MAX_INTENTOS_OUTBOX = 10
_LOCK_LOCAL_OUTBOX = threading.Lock()
_NOMBRE_LOCK_OUTBOX = "librospe_outbox_dispatcher"


def amqp_url():
    """URL AMQP del broker (vacia si no hay broker configurado).

    Se lee en cada llamada: el .env se carga al importar la app, despues
    de importar este modulo.
    """
    return (os.environ.get("AMQP_URL", "") or "").strip()


def broker_configurado():
    return bool(amqp_url())


def _ping_broker():
    """Sondeo corto (no publica). Actualiza _estado['broker']."""
    global _ultimo_ping_broker
    if not broker_configurado():
        _estado["broker"] = False
        _estado["ultimo_error"] = "AMQP_URL no configurado"
        return
    url = amqp_url()
    pika = _pika()
    if pika is None:
        _estado["broker"] = False
        _estado["ultimo_error"] = "la libreria 'pika' no esta instalada"
        return
    try:
        parametros = pika.URLParameters(url)
        parametros.heartbeat = 10
        parametros.blocked_connection_timeout = 3
        parametros.socket_timeout = 3
        parametros.connection_attempts = 1
        parametros.retry_delay = 0
        conexion = pika.BlockingConnection(parametros)
        try:
            conexion.close()
        except Exception:
            pass
        _estado["broker"] = True
        _estado["ultimo_error"] = ""
    except Exception as e:
        _estado["broker"] = False
        _estado["ultimo_error"] = str(e)[:200]
    _ultimo_ping_broker = time.monotonic()


def estado(sondear=True):
    """Estado del agente de mensajes (para el monitor /api/health).

    Si AMQP_URL está definido, sondea el broker (cache 20 s). Antes el
    health decía 'no disponible' hasta el primer publish de la vida del
    proceso, aunque el broker estuviera bien.
    """
    info = dict(_estado)
    info["broker_configurado"] = broker_configurado()
    if sondear and broker_configurado():
        if (time.monotonic() - _ultimo_ping_broker) >= _CACHE_PING_S:
            _ping_broker()
            info = dict(_estado)
            info["broker_configurado"] = True
    return info


# ------------------------------------------------------------------
# Outbox: cola local de respaldo (tabla eventos_pendientes)
# ------------------------------------------------------------------
def _db():
    """Import perezoso de la app (evita dependencia circular)."""
    from app import app, db
    return app, db


_DDL_OUTBOX = """
CREATE TABLE IF NOT EXISTS eventos_pendientes (
    id INT(11) NOT NULL AUTO_INCREMENT,
    tipo VARCHAR(80) NOT NULL,
    origen VARCHAR(40) NULL,
    payload TEXT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    intentos INT(11) NOT NULL DEFAULT 0,
    proximo_intento DATETIME NULL,
    error TEXT NULL,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    enviado_en DATETIME NULL,
    PRIMARY KEY (id),
    KEY idx_estado (estado),
    KEY idx_tipo (tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def _engine(db, bind_key=None):
    return db.engines[bind_key] if bind_key else db.engine


def _asegurar_outbox(bind_key=None):
    """Crea el outbox en la BD elegida; no confirma otras transacciones."""
    try:
        app, db = _db()
        with app.app_context():
            with _engine(db, bind_key).begin() as con:
                con.execute(text(_DDL_OUTBOX))
                if con.dialect.name in ("mysql", "mariadb"):
                    tiene_backoff = con.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema=DATABASE() AND table_name='eventos_pendientes' "
                        "AND column_name='proximo_intento'")).scalar()
                    if not tiene_backoff:
                        try:
                            con.execute(text(
                                "ALTER TABLE eventos_pendientes "
                                "ADD COLUMN proximo_intento DATETIME NULL"))
                        except Exception:
                            # Gateway y worker pueden arrancar a la vez. Si
                            # ambos observaron la columna ausente, aceptar que
                            # el otro proceso haya ganado la carrera del DDL.
                            existe_ahora = con.execute(text(
                                "SELECT COUNT(*) FROM information_schema.columns "
                                "WHERE table_schema=DATABASE() "
                                "AND table_name='eventos_pendientes' "
                                "AND column_name='proximo_intento'")).scalar()
                            if not existe_ahora:
                                raise
        return True
    except Exception as e:
        print(f"[mensajeria] no se pudo preparar el outbox: {str(e)[:180]}")
        return False


def preparar_outbox(bind_key=None):
    """Prepara una tabla outbox antes de abrir la transaccion del negocio."""
    return _asegurar_outbox(bind_key)


def guardar_en_outbox_transaccional(connection, tipo, datos, origen="gateway"):
    """Inserta un evento usando la transaccion activa del documento de ventas."""
    connection.execute(
        text("INSERT INTO eventos_pendientes (tipo, origen, payload, estado) "
             "VALUES (:t, :o, :p, 'pendiente')"),
        {"t": tipo, "o": origen,
         "p": json.dumps(datos, ensure_ascii=False, default=str)},
    )


def guardar_en_outbox(tipo, datos, origen="gateway", bind_key=None):
    """Guarda el evento en el outbox. Devuelve True si se guardo."""
    try:
        app, db = _db()
        with app.app_context():
            if not _asegurar_outbox(bind_key):
                return False
            engine = _engine(db, bind_key)
            with engine.begin() as con:
                con.execute(text(
                    "INSERT INTO eventos_pendientes (tipo, origen, payload, estado) "
                    "VALUES (:t, :o, :p, 'pendiente')"),
                    {"t": tipo, "o": origen,
                     "p": json.dumps(datos, ensure_ascii=False, default=str)})
                n = con.execute(text(
                    "SELECT COUNT(*) FROM eventos_pendientes "
                    "WHERE estado='pendiente'")).scalar()
            _estado["en_outbox"] = int(n or 0)
        return True
    except Exception as e:
        print(f"[mensajeria] no se pudo guardar en el outbox: {str(e)[:180]}")
        return False


def pendientes_outbox(limite=100, bind_key=None):
    """Devuelve eventos pendientes de la base predeterminada o de un bind."""
    try:
        app, db = _db()
        with app.app_context():
            if not _asegurar_outbox(bind_key):
                return []
            with _engine(db, bind_key).connect() as con:
                filas = con.execute(text(
                    "SELECT id, tipo, origen, payload, intentos "
                    "FROM eventos_pendientes WHERE estado='pendiente' "
                    "AND (proximo_intento IS NULL OR proximo_intento <= NOW()) "
                    "ORDER BY id LIMIT :lim"), {"lim": limite}).fetchall()
            return [{"id": f[0], "tipo": f[1], "origen": f[2],
                     "datos": json.loads(f[3]) if f[3] else {}, "intentos": f[4]}
                    for f in filas]
    except Exception as e:
        print(f"[mensajeria] no se pudieron leer los pendientes: {str(e)[:180]}")
        return []


def marcar_outbox(evento_id, ok, error=None, bind_key=None):
    """Marca el evento en la misma base desde la que fue le?do."""
    try:
        app, db = _db()
        with app.app_context():
            engine = _engine(db, bind_key)
            with engine.begin() as con:
                if ok:
                    con.execute(text(
                        "UPDATE eventos_pendientes SET estado='enviado', "
                        "enviado_en=NOW(), error=NULL, proximo_intento=NULL "
                        "WHERE id=:id"), {"id": evento_id})
                else:
                    con.execute(text(
                        "UPDATE eventos_pendientes SET "
                        "estado=CASE WHEN intentos+1 >= :max_intentos "
                        "THEN 'fallido' ELSE estado END, "
                        "error=:e, "
                        "proximo_intento=CASE WHEN intentos+1 >= :max_intentos "
                        "THEN NULL ELSE DATE_ADD(NOW(), INTERVAL "
                        "LEAST(300, 5 * POW(2, intentos)) SECOND) END "
                        ", intentos=intentos+1 "
                        "WHERE id=:id AND estado='pendiente'"),
                        {"id": evento_id, "e": (error or "")[:500],
                         "max_intentos": MAX_INTENTOS_OUTBOX})
    except Exception as e:
        print(f"[mensajeria] no se pudo marcar el outbox: {str(e)[:180]}")


def reencolar_fallidos(limite=100, tipo=None):
    """Reinicia una cantidad acotada de eventos fallidos por accion admin."""
    try:
        app, db = _db()
        total = 0
        with app.app_context():
            for bind_key in (None, "ventas"):
                if not _asegurar_outbox(bind_key):
                    continue
                engine = _engine(db, bind_key)
                with engine.connect() as con:
                    sql = "SELECT id FROM eventos_pendientes WHERE estado='fallido'"
                    parametros = {"lim": max(0, limite - total)}
                    if tipo:
                        sql += " AND tipo=:tipo"
                        parametros["tipo"] = tipo
                    sql += " ORDER BY id LIMIT :lim"
                    ids = [row[0] for row in con.execute(text(sql), parametros)]
                if not ids:
                    continue
                with engine.begin() as con:
                    for evento_id in ids:
                        con.execute(text(
                            "UPDATE eventos_pendientes SET estado='pendiente', "
                            "intentos=0, proximo_intento=NULL, error=NULL "
                            "WHERE id=:id AND estado='fallido'"), {"id": evento_id})
                        total += 1
                if total >= limite:
                    break
        return total
    except Exception as e:
        print(f"[mensajeria] no se pudieron reencolar eventos fallidos: {str(e)[:180]}")
        return 0


def procesar_outbox(limite=100):
    """Reintenta los outbox locales y el outbox atomico de ventas."""
    if not _LOCK_LOCAL_OUTBOX.acquire(blocking=False):
        return 0, 0
    conexion_lock = None
    enviados = fallidos = 0
    try:
        app, db = _db()
        with app.app_context():
            conexion_lock = db.engines["ventas"].connect()
            if conexion_lock.dialect.name in ("mysql", "mariadb"):
                tomado = conexion_lock.execute(
                    text("SELECT GET_LOCK(:nombre, 0)"),
                    {"nombre": _NOMBRE_LOCK_OUTBOX},
                ).scalar()
                if tomado != 1:
                    conexion_lock.close()
                    conexion_lock = None
                    return 0, 0
            for bind_key in (None, "ventas"):
                for ev in pendientes_outbox(limite, bind_key):
                    ok, detalle = _publicar_en_broker(
                        ev["tipo"], ev["datos"], ev.get("origen") or "gateway")
                    if ok:
                        marcar_outbox(ev["id"], True, bind_key=bind_key)
                        enviados += 1
                    else:
                        marcar_outbox(ev["id"], False, detalle, bind_key=bind_key)
                        fallidos += 1
        _estado["en_outbox"] = fallidos
        return enviados, fallidos
    finally:
        if conexion_lock is not None:
            try:
                if conexion_lock.dialect.name in ("mysql", "mariadb"):
                    conexion_lock.execute(
                        text("SELECT RELEASE_LOCK(:nombre)"),
                        {"nombre": _NOMBRE_LOCK_OUTBOX},
                    )
            except Exception:
                pass
            finally:
                conexion_lock.close()
        _LOCK_LOCAL_OUTBOX.release()


# ------------------------------------------------------------------
# Publicacion en RabbitMQ
# ------------------------------------------------------------------
def _pika():
    try:
        import pika
        return pika
    except ImportError:
        return None


def _conexion():
    """Abre una conexion AMQP (o None si no hay broker/pika)."""
    url = amqp_url()
    if not url:
        return None, "AMQP_URL no configurado"
    pika = _pika()
    if pika is None:
        return None, "la libreria 'pika' no esta instalada"
    try:
        parametros = pika.URLParameters(url)
        parametros.heartbeat = 30
        parametros.blocked_connection_timeout = 10
        parametros.connection_attempts = 2
        parametros.retry_delay = 1
        return pika.BlockingConnection(parametros), ""
    except Exception as e:
        return None, str(e)[:200]


def _publicar_en_broker(tipo, datos, origen="gateway"):
    """Publica un evento. Devuelve (ok, detalle)."""
    conexion, error = _conexion()
    if conexion is None:
        return False, error
    try:
        pika = _pika()
        canal = conexion.channel()
        canal.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
        # Confirmacion del broker: hay que activarla ANTES de publicar, para que
        # basic_publish lanze NackError/UnroutableError si el broker no lo acepta.
        if hasattr(canal, "confirm_delivery"):
            canal.confirm_delivery()
        cuerpo = json.dumps({
            "tipo": tipo,
            "origen": origen,
            "datos": datos,
            "emitido_en": datetime.now().isoformat(),
        }, ensure_ascii=False, default=str)
        props = pika.BasicProperties(content_type="application/json",
                                     delivery_mode=2,  # persistente
                                     type=tipo)
        canal.basic_publish(exchange=EXCHANGE, routing_key=tipo, body=cuerpo.encode("utf-8"),
                            properties=props)
        try:
            conexion.close()
        except Exception:
            pass
        _estado["broker"] = True
        _estado["ultimo_error"] = ""
        return True, "publicado"
    except Exception as e:
        try:
            conexion.close()
        except Exception:
            pass
        _estado["broker"] = False
        _estado["ultimo_error"] = str(e)[:200]
        return False, str(e)[:200]


def publicar_evento(tipo, datos, origen="gateway", outbox_si_falla=True):
    """Publica un evento del dominio.

    Si hay broker -> se publica.
    Si no hay broker (o falla) -> se guarda en el outbox para reintentar.
    Devuelve (publicado: bool, detalle: str).
    """
    _estado["ultimo_intento"] = datetime.now().isoformat()
    _estado["ultimo_evento"] = tipo
    ok, detalle = _publicar_en_broker(tipo, datos, origen)
    if ok:
        _estado["publicados"] += 1
        return True, detalle
    if outbox_si_falla:
        guardo = guardar_en_outbox(tipo, datos, origen)
        return False, (detalle or "") + (" | guardado en outbox" if guardo else " | SIN outbox")
    return False, detalle


# ------------------------------------------------------------------
# Consumo (lo usan los microservicios)
# ------------------------------------------------------------------
def _declarar_canal(pika, canal, servicio):
    canal.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    cola = COLAS.get(servicio, COLAS["ventas"])
    canal.queue_declare(queue=cola, durable=True)
    canal.queue_declare(queue=f"{cola}.dead", durable=True)
    for tipo, servicios in EVENTOS.items():
        if servicio in servicios:
            canal.queue_bind(exchange=EXCHANGE, queue=cola, routing_key=tipo)
    return cola


MAX_REINTENTOS_EVENTO = 3
HEADER_REINTENTOS_EVENTO = "x-librospe-reintentos"


def _publicar_reintento_o_fallido(pika, canal, cola, properties, body):
    """Reencola con limite y mueve fallos persistentes a una cola durable."""
    headers = dict(getattr(properties, "headers", None) or {})
    intentos = int(headers.get(HEADER_REINTENTOS_EVENTO, 0) or 0)
    destino = cola if intentos < MAX_REINTENTOS_EVENTO else f"{cola}.dead"
    if destino == cola:
        headers[HEADER_REINTENTOS_EVENTO] = intentos + 1
    else:
        print(f"[rabbit] mensaje apartado en {destino} tras {intentos} reintentos")
    nuevas = pika.BasicProperties(
        content_type=getattr(properties, "content_type", "application/json"),
        type=getattr(properties, "type", None),
        delivery_mode=2,
        headers=headers,
    )
    canal.basic_publish(exchange="", routing_key=destino, body=body,
                        properties=nuevas, mandatory=True)


def consumir_eventos(servicio, handler, mientras=True):
    """Consume los eventos de un microservicio.

    handler(tipo, datos) -> bool (True = procesado OK).
    Si no hay broker, devuelve False y no hace nada (el servicio sigue
    trabajando con la sincronizacion por SQL).
    """
    conexion, error = _conexion()
    if conexion is None:
        print(f"[mensajeria] {servicio}: sin broker ({error})")
        return False
    pika = _pika()
    try:
        canal = conexion.channel()
        cola = _declarar_canal(pika, canal, servicio)
        if hasattr(canal, "confirm_delivery"):
            canal.confirm_delivery()
        # Con prefetch=1 el broker entrega un evento a la vez y espera el ack
        # (si el handler falla, el basic_nack lo reencola sin perderlo).
        try:
            canal.basic_qos(prefetch_count=1)
        except Exception:
            pass
        # consume() es push: el broker empuja los eventos en cuanto llegan,
        # sin sondear la cola ni dormir entre consultas.
        entregas = canal.consume(queue=cola, auto_ack=False,
                                 inactivity_timeout=None if mientras else 0.5)
        print(f"[mensajeria] {servicio}: escuchando la cola '{cola}'")
        while True:
            metodo, properties, body = next(entregas)
            if metodo is None:
                # (None, None, None) = inactividad transcurrida
                if not mientras:
                    break
                continue
            try:
                evento = json.loads(body.decode("utf-8"))
                tipo = evento.get("tipo") or properties.type
                datos = evento.get("datos") or {}
                ok = handler(tipo, datos)
            except Exception as e:
                print(f"[mensajeria] {servicio}: error procesando el evento: {e}")
                ok = False
            if ok:
                canal.basic_ack(metodo.delivery_tag)
            else:
                try:
                    _publicar_reintento_o_fallido(pika, canal, cola, properties, body)
                    canal.basic_ack(metodo.delivery_tag)
                except Exception as e:
                    print(f"[mensajeria] no se pudo transferir el mensaje: {str(e)[:160]}")
                    canal.basic_nack(metodo.delivery_tag, requeue=True)
            if not mientras:
                break
        try:
            canal.cancel()
        except Exception:
            pass
    except Exception as e:
        print(f"[mensajeria] {servicio}: error del consumidor: {e}")
        return False
    finally:
        try:
            conexion.close()
        except Exception:
            pass
    return True
