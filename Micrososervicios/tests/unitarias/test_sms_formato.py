"""Pruebas UNITARIAS: normalizacion y composicion de SMS (sin red, sin BD)."""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))

import sms_service  # noqa: E402

pytestmark = pytest.mark.unitarias


def test_numero_de_9_digitos_gana_51():
    assert sms_service.normalizar_numero("987654321") == "51987654321"


def test_numero_con_cero_inicial():
    assert sms_service.normalizar_numero("0987654321") == "51987654321"


def test_numero_internacional_con_mas_y_espacios():
    assert sms_service.normalizar_numero("+51 987 654 321") == "51987654321"


def test_numero_ya_internacional_se_conserva():
    assert sms_service.normalizar_numero("51987654321") == "51987654321"


def test_numeros_invalidos_devuelven_none():
    assert sms_service.normalizar_numero(None) is None
    assert sms_service.normalizar_numero("") is None
    assert sms_service.normalizar_numero("abc") is None
    assert sms_service.normalizar_numero("123") is None


def test_mensaje_limpia_espacios_y_conserva_saltos():
    texto = sms_service.normalizar_mensaje("  Hola   mundo \n\n  Bien  ")
    assert texto == "Hola mundo\nBien"


def test_mensaje_recorta_en_320_con_ellipsis():
    texto = sms_service.normalizar_mensaje("x" * 500)
    assert len(texto) == 320
    assert texto.endswith("…")


def test_componer_texto_incluye_titular_y_total():
    texto = sms_service.componer_texto(
        "Boleta", "B001-000007", "Ana Prueba", 25.5,
        enlace="https://tienda.example/b/7")
    assert "Librería Salesiana Don Bosco" in texto
    assert "Boleta N° B001-000007" in texto
    assert "Cliente: Ana Prueba" in texto
    assert "Total: S/ 25.50" in texto
    assert "https://tienda.example/b/7" in texto


def test_componer_texto_sin_nombre_omite_linea_cliente():
    texto = sms_service.componer_texto("Factura", "F001-000001", "", 10)
    assert "Cliente:" not in texto
    assert "Total: S/ 10.00" in texto


def test_proveedor_configurado(monkeypatch):
    monkeypatch.delenv("SMS_PROVIDER", raising=False)
    assert sms_service.proveedor() == ""
    assert not sms_service.hay_proveedor()
    monkeypatch.setenv("SMS_PROVIDER", "twilio")
    assert sms_service.hay_proveedor()
    monkeypatch.setenv("SMS_PROVIDER", "basura")
    assert not sms_service.hay_proveedor()
