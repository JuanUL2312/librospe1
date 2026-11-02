"""El correo y PDF del checkout incluyen el desglose real del pedido."""
from datetime import datetime
from pathlib import Path
import sys

WWW = Path(__file__).resolve().parents[1] / "www"
sys.path.insert(0, str(WWW))

import app as gateway  # noqa: E402


def _pedido_email(monkeypatch, metodo_pago):
    import smtplib
    pdf_args = {}

    class SMTPFalso:
        mensaje = None

        def __init__(self, *args, **kwargs):
            pass

        def starttls(self):
            pass

        def login(self, *args):
            pass

        def send_message(self, mensaje):
            self.mensaje = mensaje
            SMTPFalso.mensaje = mensaje

        def quit(self):
            pass

    monkeypatch.setattr(smtplib, "SMTP", SMTPFalso)
    def pdf_falso(**kwargs):
        pdf_args.update(kwargs)
        return b"%PDF-test"

    monkeypatch.setattr(gateway, "generar_comprobante_pdf", pdf_falso)
    enviado = gateway.enviar_comprobante_email(
        destinatario="cliente@example.test",
        cliente_nombre="Cliente de Prueba",
        tipo_comprobante="boleta",
        numero_comprobante="B001-000001",
        fecha=datetime(2026, 10, 30, 12, 0),
        productos=[{"nombre": "Libro", "cantidad": 2,
                    "precio_unitario": 54, "total": 108}],
        total_venta=123,
        subtotal=108,
        costo_envio=12,
        cargo_contraentrega=3,
        metodo_pago=metodo_pago,
        tipo_entrega="delivery",
    )
    assert enviado is True
    mensaje = SMTPFalso.mensaje
    html = next(p.get_payload(decode=True).decode("utf-8")
                for p in mensaje.walk() if p.get_content_type() == "text/html")
    return html, pdf_args


def test_email_muestra_subtotal_envio_y_contraentrega_solo_si_corresponde(monkeypatch):
    html, pdf_args = _pedido_email(monkeypatch, "contraentrega")
    assert "Subtotal" in html and "108.00" in html
    assert "Envío" in html and "12.00" in html
    assert "Contraentrega" in html and "3.00" in html
    assert "123.00" in html
    assert pdf_args["subtotal"] == 108
    assert pdf_args["costo_envio"] == 12
    assert pdf_args["cargo_contraentrega"] == 3
    assert pdf_args["metodo_pago"] == "contraentrega"

    html_sin_contraentrega, _ = _pedido_email(monkeypatch, "yape")
    assert "Subtotal" in html_sin_contraentrega
    assert "Envío" in html_sin_contraentrega
    assert "Contraentrega" not in html_sin_contraentrega


def test_pdf_adjunto_muestra_desglose(monkeypatch):
    from reportlab import platypus

    tablas = []
    tabla_original = platypus.Table
    monkeypatch.setattr(gateway, "emitir_comprobante", lambda datos: {
        "rotulo": "Comprobante de prueba", "autorizacion": "TEST"
    })

    def tabla_capturada(datos, *args, **kwargs):
        tablas.append(datos)
        return tabla_original(datos, *args, **kwargs)

    monkeypatch.setattr(platypus, "Table", tabla_capturada)
    pdf = gateway.generar_comprobante_pdf(
        tipo_comprobante="factura",
        numero_comprobante="F001-000001",
        fecha=datetime(2026, 10, 30, 12, 0),
        cliente_nombre="Cliente de Prueba",
        productos=[{"nombre": "Libro", "cantidad": 2,
                    "precio_unitario": 54, "total": 108}],
        subtotal=108,
        costo_envio=12,
        cargo_contraentrega=3,
        metodo_pago="contraentrega",
        tipo_entrega="delivery",
        total_venta=123,
    )
    assert pdf.startswith(b"%PDF")
    resumen = tablas[1]
    etiquetas = [str(fila[2]) for fila in resumen
                 if fila[2] in ("Subtotal", "Envío", "Contraentrega", "TOTAL")]
    assert etiquetas == ["Subtotal", "Envío", "Contraentrega", "TOTAL"]


def test_pos_conserva_el_panel_lateral():
    css = (WWW / "static" / "css" / "pos_rapido.css").read_text(encoding="utf-8")
    assert "body.pos-tactil .navbar { display: none; }" in css
    assert "body.pos-tactil .panel-salesiano-wrapper { display: none; }" not in css


def test_filtro_productos_no_se_restaura_al_paginar():
    js = WWW / "static" / "js"
    filtro = (js / "productos.js").read_text(encoding="utf-8")
    paginador = (js / "paginar_tablas.js").read_text(encoding="utf-8")
    assert "data-filtro-oculto" in filtro
    assert "hasAttribute('data-filtro-oculto')" in paginador
