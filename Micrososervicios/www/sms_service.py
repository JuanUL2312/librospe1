"""Envío de mensajes SMS al cliente (comprobante de compra).

El proveedor se elige con la variable SMS_PROVIDER en .env:

  twilio     -> SMS_TWILIO_SID, SMS_TWILIO_TOKEN, SMS_TWILIO_FROM
  textlocal  -> SMS_TEXTLOCAL_USER, SMS_TEXTLOCAL_PASS, SMS_TEXTLOCAL_FROM
  webhook    -> SMS_WEBHOOK_URL, SMS_WEBHOOK_TOKEN (cualquier gateway propio)
  (vacio)    -> no hay proveedor configurado: no se envía SMS y el checkout
                cae automáticamente al envío por correo.

Si no se configura nada, el módulo NO falla: devuelve (False, motivo) para
que la compra se complete igual por el canal alternativo.

Nunca lanza excepciones.
"""
import json
import os
import urllib.parse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# =========================================================
# CONFIGURACIÓN
# =========================================================


def proveedor():
    """Nombre del proveedor configurado (vacío si no hay ninguno)."""
    return (os.environ.get("SMS_PROVIDER", "") or "").strip().lower()


def hay_proveedor():
    return proveedor() in ("twilio", "textlocal", "webhook")


# =========================================================
# TELÉFONO
# =========================================================


def normalizar_numero(telefono):
    """Normaliza a formato internacional sin '+' (51987654321).

    Acepta 987654321 / 0987654321 / 51987654321 / +51987654321.
    Devuelve None si no hay un número utilizable.
    """
    if not telefono:
        return None
    solo = "".join(ch for ch in str(telefono) if ch.isdigit())
    if not solo:
        return None
    if solo.startswith("51") and len(solo) >= 11:
        return solo
    if solo.startswith("0") and len(solo) >= 9:
        return "51" + solo[1:]
    if len(solo) == 9:
        return "51" + solo
    if len(solo) >= 8:
        return solo
    return None


def normalizar_mensaje(mensaje, maximo=320):
    """Limpia el texto (espacios sobrantes) y recorta al límite del SMS.

    Conserva los saltos de línea: el comprobante se lee mejor en varias
    líneas que en un solo párrafo.
    """
    crudo = str(mensaje or "")
    lineas = [" ".join(linea.split()) for linea in crudo.split("\n")]
    texto = "\n".join(linea for linea in lineas if linea)
    if len(texto) > maximo:
        texto = texto[:maximo - 1].rstrip() + "…"
    return texto


# =========================================================
# TEXTO DEL MENSAJE
# =========================================================


def componer_texto(titulo_comprobante, numero_comprobante, cliente_nombre,
                   total, enlace=None):
    """Arma el texto del SMS con los datos del comprobante."""
    lineas = [
        "📚 Librería Salesiana Don Bosco",
        f"{titulo_comprobante} N° {numero_comprobante}",
    ]
    nombre = (cliente_nombre or "").strip()
    if nombre:
        lineas.append(f"Cliente: {nombre}")
    lineas.append(f"Total: S/ {float(total):.2f}")
    if enlace:
        lineas.append(f"Comprobante: {enlace}")
    return normalizar_mensaje("\n".join(lineas))


# =========================================================
# ENVÍO
# =========================================================


def _post_json(url, datos, cabeceras=None, timeout=20):
    """POST JSON. Devuelve (ok, texto_respuesta)."""
    cuerpo = json.dumps(datos).encode("utf-8")
    req = Request(url, data=cuerpo, method="POST")
    req.add_header("Content-Type", "application/json")
    for nombre, valor in (cabeceras or {}).items():
        if valor:
            req.add_header(nombre, valor)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300, resp.read().decode("utf-8", "replace")
    except HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
    except URLError as e:
        return False, f"sin conexión: {e.reason}"
    except Exception as e:  # pragma: no cover - red
        return False, str(e)


def _post_form(url, datos, cabeceras=None, timeout=20):
    """POST application/x-www-form-urlencoded. Devuelve (ok, texto_respuesta)."""
    cuerpo = urllib.parse.urlencode(datos).encode("utf-8")
    req = Request(url, data=cuerpo, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    for nombre, valor in (cabeceras or {}).items():
        if valor:
            req.add_header(nombre, valor)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300, resp.read().decode("utf-8", "replace")
    except HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
    except URLError as e:
        return False, f"sin conexión: {e.reason}"
    except Exception as e:  # pragma: no cover - red
        return False, str(e)


def _enviar_twilio(numero, mensaje):
    sid = (os.environ.get("SMS_TWILIO_SID", "") or "").strip()
    token = (os.environ.get("SMS_TWILIO_TOKEN", "") or "").strip()
    origen = (os.environ.get("SMS_TWILIO_FROM", "") or "").strip()
    if not (sid and token and origen):
        return False, "faltan SMS_TWILIO_SID / SMS_TWILIO_TOKEN / SMS_TWILIO_FROM"
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    import base64
    cabeceras = {"Authorization": "Basic " + base64.b64encode(
        f"{sid}:{token}".encode("utf-8")).decode("ascii")}
    ok, detalle = _post_form(url, {"To": numero, "From": origen, "Body": mensaje},
                             cabeceras)
    return ok, detalle


def _enviar_textlocal(numero, mensaje):
    usuario = (os.environ.get("SMS_TEXTLOCAL_USER", "") or "").strip()
    clave = (os.environ.get("SMS_TEXTLOCAL_PASS", "") or "").strip()
    origen = (os.environ.get("SMS_TEXTLOCAL_FROM", "") or "").strip() or "LibreriaSalesiana"
    if not (usuario and clave):
        return False, "faltan SMS_TEXTLOCAL_USER / SMS_TEXTLOCAL_PASS"
    url = "https://api.textlocal.in/send"
    ok, detalle = _post_form(url, {
        "username": usuario,
        "password": clave,
        "from": origen,
        "to": numero,
        "message": mensaje,
    })
    return ok, detalle


def _enviar_webhook(numero, mensaje):
    url = (os.environ.get("SMS_WEBHOOK_URL", "") or "").strip()
    token = (os.environ.get("SMS_WEBHOOK_TOKEN", "") or "").strip()
    if not url:
        return False, "falta SMS_WEBHOOK_URL"
    cabeceras = {}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    ok, detalle = _post_json(url, {"telefono": numero, "mensaje": mensaje}, cabeceras)
    return ok, detalle


def enviar_sms(telefono, mensaje):
    """Envía el SMS. Devuelve (enviado: bool, detalle: str).

    No lanza excepciones: ante cualquier error devuelve (False, motivo).
    """
    numero = normalizar_numero(telefono)
    if not numero:
        return False, "teléfono no válido"
    texto = normalizar_mensaje(mensaje)
    if not texto:
        return False, "mensaje vacío"
    prov = proveedor()
    if not prov:
        return False, "sin proveedor de SMS configurado (SMS_PROVIDER)"
    try:
        if prov == "twilio":
            ok, detalle = _enviar_twilio(numero, texto)
        elif prov == "textlocal":
            ok, detalle = _enviar_textlocal(numero, texto)
        elif prov == "webhook":
            ok, detalle = _enviar_webhook(numero, texto)
        else:
            return False, f"proveedor de SMS desconocido: {prov}"
    except Exception as e:  # pragma: no cover - red
        return False, str(e)
    return ok, (detalle or "")[:300]
