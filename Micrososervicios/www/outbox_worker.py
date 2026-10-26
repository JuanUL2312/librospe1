"""Worker duradero para volver a publicar eventos pendientes del Outbox."""
import logging
import os
import signal
import time

os.environ.setdefault("OUTBOX_WORKER", "1")
from mensajeria import procesar_outbox
from app import reconciliar_reservas_stock

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("outbox-worker")
detener = False


def _solicitar_detencion(_signum, _frame):
    global detener
    detener = True


signal.signal(signal.SIGTERM, _solicitar_detencion)
signal.signal(signal.SIGINT, _solicitar_detencion)

try:
    intervalo = max(5, min(300, int(os.environ.get("OUTBOX_POLL_SECONDS", "15"))))
except (TypeError, ValueError):
    intervalo = 15

logger.info("Worker Outbox activo; intervalo=%ss", intervalo)
while not detener:
    try:
        enviados, fallidos = procesar_outbox(200)
        confirmadas, canceladas, pendientes = reconciliar_reservas_stock(200)
        if enviados or fallidos or confirmadas or canceladas or pendientes:
            logger.info("Ciclo: eventos_enviados=%s eventos_con_error=%s "
                        "reservas_confirmadas=%s pedidos_cancelados=%s "
                        "stock_pendiente=%s",
                        enviados, fallidos, confirmadas, canceladas, pendientes)
    except Exception:
        logger.exception("Fallo inesperado procesando el Outbox")
    for _ in range(intervalo):
        if detener:
            break
        time.sleep(1)

logger.info("Worker Outbox detenido")
