"""Carga de .env para el gateway (tienda y API).

setdefault: no pisa variables ya definidas por uWSGI, salvo SECRET_KEY
comprometida (estuvo en claro en uwsgi.conf y en el repositorio).
"""
import os
from pathlib import Path

# Clave histórica inyectada por uWSGI. Ya no es secreta: si sigue en el
# entorno, se deja que ~/.env la reemplace.
_CLAVE_UWSGI_FILTRADA = "Librospe@2024#ClaveUltraSecreta!"


def _es_clave_filtrada(valor):
    return bool(valor) and valor == _CLAVE_UWSGI_FILTRADA


def _parse_env(ruta: Path) -> dict:
    datos = {}
    if not ruta.is_file():
        return datos
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        datos[clave.strip()] = valor.strip().strip('"').strip("'")
    return datos


def rutas_env(desde_archivo: Path):
    """Orden: carpeta padre (repo o $HOME), $HOME, carpeta del módulo."""
    vistos = []
    candidatos = (
        desde_archivo.resolve().parent.parent / ".env",
        Path.home() / ".env",
        desde_archivo.resolve().parent / ".env",
    )
    for ruta in candidatos:
        try:
            resuelta = ruta.resolve()
        except OSError:
            continue
        if resuelta not in vistos:
            vistos.append(resuelta)
    return vistos


def cargar_entorno(desde_archivo):
    """Carga .env en os.environ. `desde_archivo` es __file__ del caller."""
    combinado = {}
    for ruta in rutas_env(Path(desde_archivo)):
        combinado.update(_parse_env(ruta))
    for clave, valor in combinado.items():
        os.environ.setdefault(clave, valor)
    actual = os.environ.get("SECRET_KEY", "")
    if _es_clave_filtrada(actual):
        nuevo = combinado.get("SECRET_KEY", "")
        if nuevo and not _es_clave_filtrada(nuevo):
            os.environ["SECRET_KEY"] = nuevo
    return combinado
