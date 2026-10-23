"""Auditoría local de peticiones del API Gateway.

Registro en archivo con RotatingFileHandler (stdlib: sin hilos extra, sin
servicios externos, apto para Alwaysdata). Una sola línea JSON por evento.
La auditoría NUNCA interrumpe la operación de negocio.
"""
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Campos que jamás se escriben en el log.
_CAMPOS_SENSIBLES = {"clave", "password", "password2", "token", "secret",
                     "autorizacion", "authorization", "csrf_token", "api_key"}

_LOGGER = None


def _logger():
    global _LOGGER
    if _LOGGER is None:
        base = os.environ.get("AUDITORIA_LOG_DIR") or str(
            Path(__file__).resolve().parent.parent / "logs"
        )
        carpeta = Path(base)
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            destino = carpeta / "auditoria_api.log"
        except OSError:
            destino = Path(os.environ.get("TEMP", ".")) / "auditoria_api.log"

        _LOGGER = logging.getLogger("librospe.auditoria_api")
        _LOGGER.setLevel(logging.INFO)
        _LOGGER.propagate = False
        if not _LOGGER.handlers:
            manejador = RotatingFileHandler(
                destino, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
            )
            manejador.setFormatter(logging.Formatter("%(message)s"))
            _LOGGER.addHandler(manejador)
        _LOGGER.destino = str(destino)
    return _LOGGER


def _resumir(payload):
    """Copia el payload eliminando secretos y limitando el tamaño."""
    if not isinstance(payload, dict):
        return payload if payload is None else str(payload)[:300]
    limpio = {}
    for k, v in payload.items():
        if str(k).lower() in _CAMPOS_SENSIBLES:
            limpio[k] = "***"
        else:
            limpio[k] = v
    texto = json.dumps(limpio, ensure_ascii=False, default=str)
    if len(texto) > 400:
        texto = texto[:400] + "…"
    return json.loads(texto) if texto else {}


def registrar(accion, metodo, ruta, estado, usuario=None, payload=None,
              request_id="", detalle=""):
    """Escribe un evento de auditoría (JSON por línea). Nunca lanza errores."""
    try:
        evento = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "accion": accion,
            "metodo": metodo,
            "ruta": ruta,
            "estado": estado,
            "usuario_id": (usuario or {}).get("id"),
            "usuario_rol": (usuario or {}).get("rol"),
            "request_id": request_id,
            "detalle": detalle,
            "payload": _resumir(payload),
        }
        _logger().info(json.dumps(evento, ensure_ascii=False, default=str))
    except Exception:
        pass
