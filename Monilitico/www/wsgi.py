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