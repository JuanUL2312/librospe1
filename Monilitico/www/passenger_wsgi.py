"""Punto de entrada WSGI para Passenger (alwaysdata).

Reutiliza :mod:`wsgi` para no duplicar la configuracion. Passenger busca por
defecto este archivo; ``.htaccess`` tambien puede apuntar a ``wsgi.py``.
"""
from wsgi import application