"""Punto de entrada WSGI para LibrosPE (local y alwaysdata).

Resuelve la raiz de la aplicacion a partir de la ubicacion de este archivo,
por lo que funciona tanto en desarrollo local (Windows) como en produccion
(alwaysdata / Passenger / uWSGI) sin cambios.
"""
import sys
import os

# Raiz de la aplicacion = directorio de este archivo (www/)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_ROOT)
os.chdir(APP_ROOT)

from app import app as application

import logging
from logging.handlers import RotatingFileHandler

_trace_handler = RotatingFileHandler(
    os.path.join(APP_ROOT, "logs", "trace.log"),
    maxBytes=2 * 1024 * 1024,
    backupCount=2,
    encoding="utf-8",
)
_trace_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.getLogger().addHandler(_trace_handler)


def _log_exception(e):
    import traceback as _tb
    try:
        with open(os.path.join(APP_ROOT, "logs", "trace.log"), "a", encoding="utf-8") as fh:
            fh.write("\n===== EXCEPCION =====\n")
            fh.write("".join(_tb.format_exception(e)))
            fh.write("\n")
    except Exception:
        pass


_orig_handle_exception = application.handle_exception


def _handle_exception(e):
    _log_exception(e)
    return _orig_handle_exception(e)


application.handle_exception = _handle_exception