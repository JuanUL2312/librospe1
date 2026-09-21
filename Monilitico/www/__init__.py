"""Entrada alternativa WSGI (algunos sitios alwaysdata cargan __init__.py).

Reexporta la app del monolito; no afecta a wsgi.py / passenger_wsgi.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as application  # noqa: E402,F401
