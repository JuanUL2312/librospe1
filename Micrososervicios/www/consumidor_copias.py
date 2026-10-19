"""Consumidor de eventos del agente de mensajes en el gateway.

En alwaysdata el gateway corre en un solo proceso uWSGI, asi que es el
propio gateway quien consume los eventos de las colas y mantiene al dia las
copias locales que cada microservicio necesita para sus JOIN.

Flujo:
    gateway publica evento -> cola del servicio -> este consumidor lo aplica
    -> la copia local del microservicio queda al dia (y el cron horario
       `procesar_eventos.sh` / `sincronizar_copias.sql` sigue siendo la red
       de seguridad).
"""
import os
import threading
import time
from pathlib import Path

from sqlalchemy import text

_candado = threading.Lock()
_hay_pendientes = threading.Event()
_ultima_aplicacion = 0.0
SERVICIOS = ("inventario", "ventas", "usuarios", "clientes")
# El script de sincronizacion de copias puede estar en la raiz del proyecto
# o junto a la app (www/).
RUTAS_SQL = (
    Path(__file__).resolve().parent.parent / "sincronizar_copias.sql",
    Path(__file__).resolve().parent / "sincronizar_copias.sql",
)


def _ruta_sql():
    for ruta in RUTAS_SQL:
        if ruta.is_file():
            return ruta
    return None


def _sentencias():
    """Divide el script de sincronizacion en sentencias (sin comentarios)."""
    ruta = _ruta_sql()
    if not ruta:
        return []
    sql = ruta.read_text(encoding="utf-8", errors="replace")
    salida = []
    for bloque in sql.split(";\n"):
        limpio = "\n".join(l for l in bloque.split("\n")
                           if l.strip() and not l.strip().startswith("--")).strip()
        if limpio:
            salida.append(limpio)
    return salida


def aplicar_copias():
    """Ejecuta la sincronizacion de copias locales (mismo SQL del cron)."""
    global _ultima_aplicacion
    with _candado:
        _ultima_aplicacion = time.time()
        try:
            from app import app, db
            sentencias = _sentencias()
            if not sentencias:
                print("[consumidor] no se encontro sincronizar_copias.sql")
                return False
            with app.app_context():
                for stmt in sentencias:
                    try:
                        db.session.execute(text(stmt))
                    except Exception as e:
                        db.session.rollback()
                        print(f"[consumidor] error al aplicar una sentencia: {str(e)[:120]}")
                        return False
                db.session.commit()
            print("[consumidor] copias locales actualizadas")
            return True
        except Exception as e:
            print(f"[consumidor] error aplicando copias: {e}")
            return False


def _hilo_aplicador():
    """Aplica las copias cuando llegan eventos (con agrupamiento de 3 s)."""
    while True:
        _hay_pendientes.wait()
        time.sleep(3)          # agrupa varios eventos seguidos
        _hay_pendientes.clear()
        aplicar_copias()


def _handler(tipo, datos):
    """Cada evento recibido marca que hay que refrescar las copias."""
    _hay_pendientes.set()
    return True


def iniciar_consumidor_copias():
    """Arranca los consumidores de las colas del agente de mensajes."""
    if not os.environ.get("AMQP_URL", "").strip():
        print("[consumidor] sin AMQP_URL: no se arrancan los consumidores")
        return False
    from mensajeria import consumir_eventos
    threading.Thread(target=_hilo_aplicador, name="consumidor-copias", daemon=True).start()
    for servicio in SERVICIOS:
        threading.Thread(target=consumir_eventos, args=(servicio, _handler),
                         name=f"consumidor-{servicio}", daemon=True).start()
    print("[consumidor] consumidores de eventos arrancados:", ", ".join(SERVICIOS))
    return True
