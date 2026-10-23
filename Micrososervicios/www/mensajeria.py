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
from datetime import datetime

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


def amqp_url():
    """URL AMQP del broker (vacia si no hay broker configurado).

    Se lee en cada llamada: el .env se carga al importar la app, despues
    de importar este modulo.
    """
    return (os.environ.get("AMQP_URL", "") or "").strip()


def broker_configurado():
    return bool(amqp_url())


def estado():
    """Estado del agente de mensajes (para el monitor /api/health)."""
    info = dict(_estado)
    info["broker_configurado"] = broker_configurado()
    return info


# ------------------------------------------------------------------
# Outbox: cola local de respaldo (tabla eventos_pendientes)
# ------------------------------------------------------------------
def _db():
    """Import perezoso de la app (evita dependencia circular)."""
    from app import app, db
    return app, db


def _asegurar_outbox():
    """Crea la tabla del outbox si no existe."""
    try:
        app, db = _db()
        with app.app_context():
            db.session.execute(db.text("""
                CREATE TABLE IF NOT EXISTS eventos_pendientes (
                    id INT(11) NOT NULL AUTO_INCREMENT,
                    tipo VARCHAR(80) NOT NULL,
                    origen VARCHAR(40) NULL,
                    payload TEXT NULL,
                    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
                    intentos INT(11) NOT NULL DEFAULT 0,
                    error TEXT NULL,
                    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    enviado_en DATETIME NULL,
                    PRIMARY KEY (id),
                    KEY idx_estado (estado),
                    KEY idx_tipo (tipo)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""))
            db.session.commit()
        return True
    except Exception as e:
        print(f"[mensajeria] no se pudo preparar el outbox: {e}")
        return False


def guardar_en_outbox(tipo, datos, origen="gateway"):
    """Guarda el evento en el outbox. Devuelve True si se guardo."""
    try:
        app, db = _db()
        with app.app_context():
            _asegurar_outbox()
            db.session.execute(db.text(
                "INSERT INTO eventos_pendientes (tipo, origen, payload, estado) "
                "VALUES (:t, :o, :p, 'pendiente')"),
                {"t": tipo, "o": origen, "p": json.dumps(datos, ensure_ascii=False, default=str)})
            db.session.commit()
            n = db.session.execute(db.text(
                "SELECT COUNT(*) FROM eventos_pendientes WHERE estado='pendiente'")).scalar()
            _estado["en_outbox"] = int(n or 0)
        return True
    except Exception as e:
        print(f"[mensajeria] no se pudo guardar en el outbox: {e}")
        return False


def pendientes_outbox(limite=100):
    """Devuelve los eventos pendientes del outbox (lista de dicts)."""
    try:
        app, db = _db()
        with app.app_context():
            _asegurar_outbox()
            filas = db.session.execute(db.text(
                "SELECT id, tipo, origen, payload, intentos FROM eventos_pendientes "
                "WHERE estado='pendiente' ORDER BY id LIMIT :lim"), {"lim": limite}).fetchall()
            return [{"id": f[0], "tipo": f[1], "origen": f[2],
                     "datos": json.loads(f[3]) if f[3] else {}, "intentos": f[4]} for f in filas]
    except Exception as e:
        print(f"[mensajeria] no se pudieron leer los pendientes: {e}")
        return []


def marcar_outbox(evento_id, ok, error=None):
    """Marca el evento del outbox como enviado o fallido."""
    try:
        app, db = _db()
        with app.app_context():
            if ok:
                db.session.execute(db.text(
                    "UPDATE eventos_pendientes SET estado='enviado', enviado_en=NOW(), error=NULL "
                    "WHERE id=:id"), {"id": evento_id})
            else:
                db.session.execute(db.text(
                    "UPDATE eventos_pendientes SET intentos=intentos+1, error=:e "
                    "WHERE id=:id"), {"id": evento_id, "e": (error or "")[:500]})
            db.session.commit()
    except Exception as e:
        print(f"[mensajeria] no se pudo marcar el outbox: {e}")


def procesar_outbox(limite=100):
    """Reintenta publicar los eventos pendientes. Devuelve (enviados, fallidos)."""
    enviados = fallidos = 0
    for ev in pendientes_outbox(limite):
        ok, detalle = _publicar_en_broker(ev["tipo"], ev["datos"], ev.get("origen") or "gateway")
        if ok:
            marcar_outbox(ev["id"], True)
            enviados += 1
        else:
            marcar_outbox(ev["id"], False, detalle)
            fallidos += 1
    _estado["en_outbox"] = fallidos
    return enviados, fallidos


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
    for tipo, servicios in EVENTOS.items():
        if servicio in servicios:
            canal.queue_bind(exchange=EXCHANGE, queue=cola, routing_key=tipo)
    return cola


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
                # se devuelve al inicio de la cola para reintentar
                try:
                    canal.basic_nack(metodo.delivery_tag, requeue=True)
                except Exception:
                    pass
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
