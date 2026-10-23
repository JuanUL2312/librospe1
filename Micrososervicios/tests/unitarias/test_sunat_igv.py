"""Pruebas UNITARIAS: calculo de IGV y payload SUNAT (sin red, sin BD).

Cubre la funcion matematica de negocio de `sunat_service._payload_invoice`:
IGV 18% solo en facturas, precio "aumentado" en boletas, tipos de documento
y totales; mas el modo simulado y el fallback de errores.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))

import sunat_service  # noqa: E402

pytestmark = pytest.mark.unitarias

VENTA = {
    "tipo_comprobante": "boleta",
    "numero": 7,
    "cliente_documento": "987654321",
    "cliente_nombre": "Ana Prueba",
    "productos": [
        {"codigo": "L001", "nombre": "Libro de Algebra", "cantidad": 2,
         "precio_unitario": 50.0},
        {"codigo": "L002", "nombre": "Cuaderno", "cantidad": 1,
         "precio_unitario": 10.0},
    ],
}


def test_boleta_no_lleva_igv():
    p = sunat_service._payload_invoice(VENTA)
    assert p["tipoDoc"] == "03"
    assert p["serie"] == "B001"
    for item in p["items"]:
        assert item["igv"] == 0.0


def test_boleta_precio_unitario_incluye_18():
    p = sunat_service._payload_invoice(VENTA)
    assert p["items"][0]["precioUnitario"] == round(50.0 * 1.18, 2)
    assert p["items"][0]["subtotal"] == 100.0
    assert p["items"][0]["total"] == 100.0


def test_factura_lleva_igv_18_por_linea():
    venta = {k: v for k, v in VENTA.items() if k != "serie"}
    venta["tipo_comprobante"] = "factura"
    p = sunat_service._payload_invoice(venta)
    assert p["tipoDoc"] == "01"
    assert p["serie"] == "F001"
    item = p["items"][0]                      # 2 x S/ 50
    assert item["precioUnitario"] == 50.0     # neto en factura
    assert item["subtotal"] == 100.0
    assert item["igv"] == round(100.0 * 0.18, 2)
    assert item["total"] == 118.0


def test_factura_total_es_suma_de_totales():
    venta = {k: v for k, v in VENTA.items() if k != "serie"}
    venta["tipo_comprobante"] = "factura"
    p = sunat_service._payload_invoice(venta)
    assert p["venta"]["total"] == round(
        sum(i["total"] for i in p["items"]), 2)


def test_documento_11_digitos_fuerza_tipo_6():
    venta = dict(VENTA, cliente_documento="20123456789")
    assert sunat_service._payload_invoice(venta)["tipoDocCliente"] == "6"


def test_boleta_dni_corto_es_tipo_1():
    p = sunat_service._payload_invoice(VENTA)
    assert p["tipoDocCliente"] == "1"
    assert p["numDocCliente"] == "987654321"


def test_modo_invalido_cae_a_simulado(monkeypatch):
    monkeypatch.delenv("SUNAT_MODE", raising=False)
    assert sunat_service.modo() == "simulado"
    monkeypatch.setenv("SUNAT_MODE", "PRODUCCION")
    assert sunat_service.modo() == "produccion"
    monkeypatch.setenv("SUNAT_MODE", "inventado")
    assert sunat_service.modo() == "simulado"


def test_emitir_simulado_no_toca_la_red(monkeypatch):
    monkeypatch.setenv("SUNAT_MODE", "simulado")
    monkeypatch.setattr(
        sunat_service, "_http",
        lambda *a, **k: pytest.fail("el modo simulado no debe llamar a la API"))
    r = sunat_service.emitir_comprobante(VENTA)
    assert r["estado"] == "SIMULADO"
    assert "SIMULADA" in r["rotulo"]


def test_emitir_beta_con_error_hace_fallback(monkeypatch):
    monkeypatch.setenv("SUNAT_MODE", "beta")

    def _boom():
        raise RuntimeError("sin credenciales")

    monkeypatch.setattr(sunat_service, "_login", _boom)
    r = sunat_service.emitir_comprobante(VENTA)
    assert r["estado"].startswith("ERROR_FALLBACK")
    assert r["modo"] == "beta"
    assert r["autorizacion"].startswith("B001-000007")


def test_estado_comprobante_simulado(monkeypatch):
    monkeypatch.setenv("SUNAT_MODE", "simulado")
    assert sunat_service.estado_comprobante("03", "B001", 1) == {
        "modo": "simulado", "estado": "SIMULADO"}
