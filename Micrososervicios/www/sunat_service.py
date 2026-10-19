"""Integración SUNAT para LibrosPE a través de APIsPERU (apisperu.com).

Tres modos configurados con ``SUNAT_MODE`` en ``.env``:

* ``simulado`` (por defecto) - sin llamadas externas; el comprobante se genera
  con un hash local y el rótulo "AUTORIZACIÓN SUNAT (SIMULADA)".
* ``beta`` - llama a la API de facturación de APIsPERU contra el ambiente de
  pruebas de SUNAT (no requiere certificado digital).
* ``produccion`` - misma API contra SUNAT producción (requiere plan de
  facturación, certificado .pfx y usuario SOL secundario cargados en el panel
  de APIsPERU).

La API se invoca en 3 pasos:

1. ``POST /auth/login`` -> token (24 h).
2. ``POST /invoice`` -> emite el comprobante (boleta 03 / factura 01) y
   devuelve el estado del CDR.
3. ``GET /invoice/status`` -> consulta puntual si la emisión queda pendiente.

Cualquier error de red o de la API hace fallback al modo ``simulado`` para
nunca interrumpir una venta (se registra con ``print`` para depuración).

Variables de entorno (ver ``.env.example``)::

    SUNAT_MODE=simulado
    FACTURACION_API_URL=https://facturacion.apisperu.com/api/v1
    FACTURACION_USER=
    FACTURACION_PASS=
"""
import json
import os
import secrets
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Tipo de documento SUNAT por comprobante
TIPOS_COMPROBANTE = {"boleta": "03", "factura": "01", "nota": "03"}

ROTULOS = {
    "simulado": "AUTORIZACIÓN SUNAT (SIMULADA)",
    "beta": "AMBIENTE DE PRUEBAS SUNAT (BETA)",
    "produccion": "AUTORIZACIÓN SUNAT",
}


def modo():
    """Modo activo: simulado | beta | produccion."""
    valor = os.environ.get("SUNAT_MODE", "simulado").strip().lower()
    return valor if valor in ROTULOS else "simulado"


def _api_url():
    return os.environ.get(
        "FACTURACION_API_URL", "https://facturacion.apisperu.com/api/v1"
    ).rstrip("/")


def _http(path, payload=None, token=None, method=None):
    """Llamada HTTP JSON a la API de facturación. Devuelve dict o lanza."""
    url = f"{_api_url()}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, method=method or ("POST" if data else "GET"))
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _login():
    usuario = os.environ.get("FACTURACION_USER", "")
    clave = os.environ.get("FACTURACION_PASS", "")
    if not usuario or not clave:
        raise RuntimeError("FACTURACION_USER/FACTURACION_PASS sin configurar")
    resp = _http("/auth/login", {"username": usuario, "password": clave})
    token = resp.get("token") or (resp.get("data") or {}).get("token")
    if not token:
        raise RuntimeError("La API no devolvió token de autenticación")
    return token


def _resumen_simulado(serie_numero):
    """Resultado en modo simulado (hash local, igual que el código anterior)."""
    return {
        "modo": modo(),
        "rotulo": ROTULOS[modo()],
        "autorizacion": f"{serie_numero} | {secrets.token_hex(8).upper()}",
        "estado": "SIMULADO",
        "cdr": None,
        "hash": None,
    }


def _payload_invoice(venta):
    """Cuerpo JSON del comprobante para la API de facturación.

    Estructura según la documentación de APIsPERU (facturacion.apisperu.com);
    validar contra el Swagger oficial la primera vez con credenciales reales.
    """
    hoy = date.today().isoformat()
    tipo = TIPOS_COMPROBANTE.get(venta.get("tipo_comprobante") or "boleta", "03")
    es_factura = tipo == "01"
    documento = str(venta.get("cliente_documento") or "").strip()
    tipo_doc = "6" if (es_factura or len(documento) == 11) else "1"
    items = []
    for i, it in enumerate(venta.get("productos") or [], start=1):
        cantidad = int(it.get("cantidad", 1) or 1)
        precio = float(it.get("precio_unitario") or 0)
        valor_venta = round(cantidad * precio, 2)
        igv = round(valor_venta * 0.18, 2) if es_factura else 0.0
        items.append({
            "codProducto": str(it.get("codigo", i)),
            "descripcion": str(it.get("nombre", ""))[:200],
            "cantidad": cantidad,
            "unidadMedida": "NIU",
            "precioUnitario": round(precio, 2) if es_factura else round(precio * 1.18, 2),
            "subtotal": valor_venta,
            "igv": igv,
            "total": round(valor_venta + igv, 2),
        })
    total = round(sum(i["total"] for i in items), 2)
    return {
        "tipoDoc": tipo,
        "serie": (venta.get("serie") or ("F001" if es_factura else "B001")),
        "numero": int(venta.get("numero") or 1),
        "fechaEmision": hoy,
        "moneda": "PEN",
        "tipoDocCliente": tipo_doc,
        "numDocCliente": documento or ("00000000001" if tipo_doc == "6" else "000000000"),
        "cliente": venta.get("cliente_nombre") or "Cliente",
        "items": items,
        "venta": {"total": total},
        "ambiente": "beta" if modo() == "beta" else "produccion",
    }


def emitir_comprobante(venta):
    """Emite (o simula) la autorización SUNAT de un comprobante de venta.

    :param venta: dict con tipo_comprobante, serie/numero, cliente_documento,
        cliente_nombre y productos [{nombre, cantidad, precio_unitario, codigo}].
    :return: dict con modo, rotulo (para el PDF), autorizacion, estado, cdr, hash.
    """
    serie_numero = venta.get("serie_numero") or (
        f"{venta.get('serie', 'B001')}-{int(venta.get('numero') or 1):06d}"
    )
    if modo() == "simulado":
        return _resumen_simulado(serie_numero)

    try:
        token = _login()
        resp = _http("/invoice", _payload_invoice(venta), token=token)
        data = resp.get("data") or resp
        estado = str(data.get("estado") or data.get("sunat_status") or "PENDIENTE").upper()
        hash_cpe = data.get("hash_cpe") or data.get("hash") or ""
        cdr = data.get("cdr") or data.get("cdr_url")
        autorizacion = f"{serie_numero} | {hash_cpe}" if hash_cpe else serie_numero
        return {
            "modo": modo(),
            "rotulo": ROTULOS[modo()],
            "autorizacion": autorizacion,
            "estado": estado,
            "cdr": cdr,
            "hash": hash_cpe or None,
        }
    except (HTTPError, URLError, OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"[SUNAT] Error en modo {modo()} ({exc}); fallback a simulado")
        resumen = _resumen_simulado(serie_numero)
        resumen["estado"] = f"ERROR_FALLBACK: {exc}"
        return resumen


def estado_comprobante(tipo, serie, numero):
    """Consulta puntual del CDR (solo modos beta/produccion)."""
    if modo() == "simulado":
        return {"modo": "simulado", "estado": "SIMULADO"}
    try:
        token = _login()
        resp = _http(
            f"/invoice/status?tipo={tipo}&serie={serie}&numero={numero}",
            token=token,
        )
        return resp.get("data") or resp
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as exc:
        return {"modo": modo(), "estado": "ERROR", "detalle": str(exc)}
