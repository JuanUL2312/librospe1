"""Consumidor de eventos del agente de mensajes (RabbitMQ) para un microservicio.

Modulo AUTONOMO: el servicio no depende del gateway. Si no hay broker
configurado (AMQP_URL vacio) o no se puede conectar, el servicio sigue
funcionando con normalidad y los eventos quedan en el outbox del gateway
(tabla eventos_pendientes) para reintentarse despues.

Uso:
    from rabbit_consumidor import iniciar_consumidor
    iniciar_consumidor("inventario", mi_handler)
"""
import json
import os
import threading

EXCHANGE = (os.environ.get("AMQP_EXCHANGE", "librospe.eventos") or "librospe.eventos").strip()

COLAS = {
    "inventario": os.environ.get("AMQP_COLA_INVENTARIO", "librospe.inventario"),
    "ventas": os.environ.get("AMQP_COLA_VENTAS", "librospe.ventas"),
    "usuarios": os.environ.get("AMQP_COLA_USUARIOS", "librospe.usuarios"),
    "clientes": os.environ.get("AMQP_COLA_CLIENTES", "librospe.clientes"),
}

# routing key -> servicios que la consumen (solo los eventos que se emiten)
EVENTOS = {
    "pedido.creado": ["inventario", "ventas"],
    "venta.registrada": ["inventario", "ventas"],
    "producto.actualizado": ["ventas", "inventario"],
    "cliente.registrado": ["ventas", "usuarios"],
    "producto.alerta_stock": ["usuarios", "ventas"],
}


def amqp_url():
    return (os.environ.get("AMQP_URL", "") or "").strip()


def _pika():
    try:
        import pika
        return pika
    except ImportError:
        return None


def _conexion():
    url = amqp_url()
    if not url:
        return None, "AMQP_URL no configurado"
    pika = _pika()
    if pika is None:
        return None, "falta la libreria 'pika' (pip install pika)"
    try:
        parametros = pika.URLParameters(url)
        parametros.heartbeat = 30
        parametros.blocked_connection_timeout = 10
        parametros.connection_attempts = 3
        parametros.retry_delay = 2
        return pika.BlockingConnection(parametros), ""
    except Exception as e:
        return None, str(e)[:200]


def _preparar_canal(pika, canal, servicio):
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


def _consumir(servicio, handler, parar):
    """Bucle de consumo (se ejecuta en un hilo)."""
    while not parar.is_set():
        conexion, error = _conexion()
        if conexion is None:
            print(f"[rabbit] {servicio}: sin broker ({error}). Reintento en 30s.")
            parar.wait(30)
            continue
        pika = _pika()
        try:
            canal = conexion.channel()
            cola = _preparar_canal(pika, canal, servicio)
            if hasattr(canal, "confirm_delivery"):
                canal.confirm_delivery()
            # prefetch=1: el broker entrega un evento a la vez y espera el ack
            try:
                canal.basic_qos(prefetch_count=1)
            except Exception:
                pass
            print(f"[rabbit] {servicio}: escuchando la cola '{cola}'")
            # consume() empuja los eventos en cuanto llegan; con el timeout
            # corto el bucle sigue revisando `parar` cada segundo.
            entregas = canal.consume(queue=cola, auto_ack=False, inactivity_timeout=1.0)
            while not parar.is_set():
                metodo, properties, body = next(entregas)
                if metodo is None:
                    continue      # inactividad: se revisa `parar` en la vuelta
                try:
                    evento = json.loads(body.decode("utf-8"))
                    tipo = evento.get("tipo") or properties.type
                    datos = evento.get("datos") or {}
                    ok = bool(handler(tipo, datos))
                except Exception as e:
                    print(f"[rabbit] {servicio}: error al procesar: {e}")
                    ok = False
                try:
                    if ok:
                        canal.basic_ack(metodo.delivery_tag)
                    else:
                        try:
                            _publicar_reintento_o_fallido(pika, canal, cola, properties, body)
                            canal.basic_ack(metodo.delivery_tag)
                        except Exception as transfer_error:
                            print(f"[rabbit] {servicio}: no se pudo transferir el mensaje: {str(transfer_error)[:160]}")
                            canal.basic_nack(metodo.delivery_tag, requeue=True)
                except Exception:
                    pass
            try:
                canal.cancel()
            except Exception:
                pass
        except Exception as e:
            print(f"[rabbit] {servicio}: error del consumidor: {e}")
            parar.wait(10)
        finally:
            try:
                conexion.close()
            except Exception:
                pass


def iniciar_consumidor(servicio, handler, daemon=True):
    """Arranca el consumidor de eventos en segundo plano.

    Devuelve el objeto `threading.Event` para poder detenerlo.
    """
    parar = threading.Event()
    hilo = threading.Thread(target=_consumir, args=(servicio, handler, parar),
                            name=f"rabbit-{servicio}", daemon=daemon)
    hilo.start()
    return parar


def salud():
    """Estado del broker para el /health del servicio."""
    conexion, error = _conexion()
    if conexion is None:
        return {"broker": "no disponible", "detalle": error, "cola": COLAS.get("ventas")}
    try:
        conexion.close()
    except Exception:
        pass
    return {"broker": "conectado", "exchange": EXCHANGE}
