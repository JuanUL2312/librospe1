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
import time

EXCHANGE = (os.environ.get("AMQP_EXCHANGE", "librospe.eventos") or "librospe.eventos").strip()

COLAS = {
    "inventario": os.environ.get("AMQP_COLA_INVENTARIO", "librospe.inventario"),
    "ventas": os.environ.get("AMQP_COLA_VENTAS", "librospe.ventas"),
    "usuarios": os.environ.get("AMQP_COLA_USUARIOS", "librospe.usuarios"),
    "clientes": os.environ.get("AMQP_COLA_CLIENTES", "librospe.clientes"),
}

# routing key -> servicios que la consumen
EVENTOS = {
    "pedido.creado": ["inventario", "ventas"],
    "venta.registrada": ["inventario", "ventas"],
    "producto.actualizado": ["ventas", "inventario"],
    "stock.actualizado": ["ventas", "inventario"],
    "cliente.registrado": ["ventas", "usuarios"],
    "cliente.actualizado": ["ventas"],
    "usuario.actualizado": ["ventas", "inventario"],
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
    for tipo, servicios in EVENTOS.items():
        if servicio in servicios:
            canal.queue_bind(exchange=EXCHANGE, queue=cola, routing_key=tipo)
    return cola


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
            print(f"[rabbit] {servicio}: escuchando la cola '{cola}'")
            while not parar.is_set():
                metodo, properties, body = canal.basic_get(queue=cola, auto_ack=False)
                if metodo is None:
                    parar.wait(1)
                    continue
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
                        canal.basic_nack(metodo.delivery_tag, requeue=True)
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
