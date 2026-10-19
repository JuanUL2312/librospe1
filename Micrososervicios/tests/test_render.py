"""Pruebas de renderizado de las plantillas principales.

Detecta errores de Jinja (variables inexistentes, bloques mal cerrados)
sin necesidad de base de datos.
"""
import pathlib
from datetime import datetime

import pytest

WWW = pathlib.Path(__file__).resolve().parent.parent / "www"
PLANTILLAS = WWW / "templates"


class ObjetoFalso:
    """Objeto con cualquier atributo (para las plantillas)."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, nombre):
        return None


def _contexto():
    return {
        "cliente": ObjetoFalso(nombres="JUAN", apellidos="PRUEBA", correo="a@b.pe",
                               telefono="987654321", dni="75535870", ruc=None, ce=None,
                               direccion="Jr. Ensayo 1", estado=1, puntos=0,
                               departamento="JUNIN", provincia="HUANCAYO", distrito="HUANCAYO",
                               fecha_registro=None, token_recuperacion=None,
                               token_expiracion=None, clave="x"),
        "pedido": ObjetoFalso(id=1, cliente_id=1, fecha_pedido=datetime(2026, 10, 19, 12, 0), estado="entregado",
                              total=14.0, subtotal=14.0, descuento=0, costo_envio=0,
                              tipo_entrega="delivery", direccion_entrega="Jr. Ensayo",
                              distrito_entrega="El Tambo", metodo_pago="efectivo",
                              cliente_confirmo=0, reporte_no_recibido=1,
                              fecha_confirmacion_cliente=None, foto_entrega=None,
                              nombre_recibe="Jose", dni_recibe=None, fecha_entrega=datetime(2026, 10, 19, 12, 30),
                              lat=None, lng=None, geo_precision=None, cargo_contraentrega=0,
                              cliente_nombres="JUAN", cliente_apellidos="PRUEBA",
                              cliente_correo="a@b.pe", cliente_telefono="987654321",
                              cliente_documento="75535870", cliente_razon_social="",
                              cliente_direccion_fiscal="", detalles=[]),
        "detalles": [],
        "venta": None,
        "pedidos": [],
        "es_admin": True,
        "now": None,
        # datos agregados del panel (dashboard) y de otras vistas
        "total_ventas_hoy": 0.0, "cantidad_ventas_hoy": 0,
        "total_ventas_mes": 0.0, "cantidad_ventas_mes": 0,
        "pedidos_pendientes": 0, "pedidos_en_proceso": 0,
        "pedidos_no_recibidos": 0, "total_clientes": 0, "clientes_nuevos": 0,
        "ticket_promedio_hoy": 0.0, "ticket_promedio_mes": 0.0,
        "margen_bruto": 0.0, "margen_pct": 0.0, "productos_con_costo": 0,
        "unidades_vendidas_30d": 0, "rotacion_inventario": 0.0, "dias_stock": 0.0,
        "conversion_pedidos": 0.0, "pedidos_convertidos": 0, "total_pedidos": 0,
        "ventas_vendedor": [], "ventas_por_dia": [], "top_productos": [],
        "stock_bajo": [], "stock_critico": [], "stock_exceso": [],
        "graph_ventas": None, "graph_top": None, "graph_cat": None,
        "graph_estados": None, "caja": None, "cajas": [], "movimientos": [],
        "historial": [], "usuarios": [], "permisos": [], "roles": [],
        "productos": [], "categorias": [], "proveedores": [], "auditorias": [],
        "bloqueos": [], "intentos": [], "ubigeo": {}, "puntos": [],
        "compras": [], "proveedores_precios": [],
    }


@pytest.mark.parametrize("plantilla", [
    "carrito.html", "checkout.html", "pedidos.html", "pedido_detalle.html",
    "mis_pedidos.html", "cliente_pedido_detalle.html", "registro_cliente.html",
    "dashboard.html", "cliente_perfil.html",
])
def test_plantilla_renderiza(plantilla):
    """Cada plantilla principal debe renderizar sin errores."""
    from flask import render_template
    from app import app
    with app.test_request_context("/"):
        html = render_template(plantilla, **_contexto())
        assert len(html) > 500, f"{plantilla} renderizo vacia"


def test_checkout_tiene_opcion_sms():
    """La opcion de SMS debe existir en el checkout."""
    from flask import render_template
    from app import app
    with app.test_request_context("/"):
        html = render_template("checkout.html", **_contexto())
        assert "cardCompSms" in html
        assert 'value="sms"' in html


def test_pedidos_muestran_el_reporte():
    """La lista de pedidos debe mostrar el badge de NO RECIBIDO."""
    from flask import render_template
    from app import app
    contexto = _contexto()
    contexto["pedidos"] = [{
        "id": 1, "fecha_pedido": None, "estado": "entregado", "total": 14.0,
        "tipo_entrega": "delivery", "direccion_entrega": "Jr. Ensayo",
        "cliente_nombres": "JUAN", "cliente_apellidos": "PRUEBA",
        "cliente_nombre_completo": "JUAN PRUEBA", "cliente_email": "a@b.pe",
        "cliente_telefono": "987654321", "reporto_no_recibido": 1,
    }]
    with app.test_request_context("/"):
        html = render_template("pedidos.html", **contexto)
        assert "NO RECIBIDO" in html
        assert 'name="reporte"' in html       # filtro de solo reportados

