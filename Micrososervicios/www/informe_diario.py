#!/usr/bin/env python3
"""Informe diario por correo de LibrosPE (para cron).

Resume las ultimas 24 horas: ventas, estado de caja, stock bajo,
pedidos nuevos y ajustes de conteo pendientes. Se envia a los
administradores.

Uso:
    python3 informe_diario.py            # envia el informe
    python3 informe_diario.py --probar   # genera y muestra en pantalla sin enviar

Programacion (ver programar_informe_diario.sh):
    30 22 * * * cd <ruta>/www && python3 informe_diario.py >> informe_diario.log 2>&1
"""
import os
import sys
from datetime import datetime, timedelta

RUTA_WWW = os.path.dirname(os.path.abspath(__file__))


def _cargar_env(ruta):
    """Carga variables de .env sin pisar las ya definidas en el entorno."""
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


# El .env vive un nivel arriba (Micrososervicios/.env), junto al README.
_cargar_env(os.path.join(os.path.dirname(RUTA_WWW), ".env"))

from app import (  # noqa: E402  (import despues de cargar el entorno)
    app, db, Venta, Producto, Caja, Pedido, ConteoStock,
    UsuarioSistema, _enviar_correo_html,
)


def _resumen_24h():
    desde = datetime.now() - timedelta(days=1)

    ventas = Venta.query.filter(Venta.fecha_venta >= desde, Venta.estado == 1).all()
    total_ventas = sum(
        float(v.cantidad) * float(v.producto.precio or 0)
        for v in ventas if v.producto
    )
    boletas = sum(1 for v in ventas if v.tipo_comprobante == "boleta")
    facturas = sum(1 for v in ventas if v.tipo_comprobante == "factura")

    bajos = Producto.query.filter(
        Producto.estado == 1,
        Producto.cantidad <= db.func.coalesce(Producto.stock_minimo, 5),
    ).all()

    caja = Caja.query.order_by(Caja.id.desc()).first()

    pedidos_nuevos = Pedido.query.filter(Pedido.fecha_pedido >= desde).count()
    pedidos_pendientes = Pedido.query.filter(
        Pedido.fecha_pedido >= desde, Pedido.estado == "pendiente").count()

    ajustes_pendientes = ConteoStock.query.filter(
        ConteoStock.ajustado == 0, ConteoStock.diferencia != 0).count()

    return {
        "desde": desde,
        "n_ventas": len(ventas),
        "total_ventas": total_ventas,
        "boletas": boletas,
        "facturas": facturas,
        "bajos": bajos,
        "caja": caja,
        "pedidos_nuevos": pedidos_nuevos,
        "pedidos_pendientes": pedidos_pendientes,
        "ajustes_pendientes": ajustes_pendientes,
    }


def _html(r):
    lineas_bajo = "".join(
        f"<li>{p.nombre}: {p.cantidad} uds (mín. "
        f"{p.stock_minimo if p.stock_minimo is not None else 5})</li>"
        for p in r["bajos"][:40]
    ) or "<li>✅ Sin alertas de stock bajo</li>"

    caja = r["caja"]
    if caja and caja.estado == "abierta":
        caja_html = (f"<p>🟡 <b>Caja ABIERTA</b> desde "
                     f"{caja.fecha_apertura.strftime('%d/%m/%Y %H:%M')} "
                     f"(queda cerrarla)</p>")
    elif caja:
        dif = float(caja.diferencia or 0)
        estado = "sin diferencia" if dif == 0 else f"diferencia S/ {dif:.2f}"
        caja_html = (f"<p>🟢 Último cierre: {caja.fecha_cierre.strftime('%d/%m/%Y %H:%M')} "
                     f"— {estado}</p>")
    else:
        caja_html = "<p>⚪ Sin registros de caja</p>"

    return f"""
    <h3>Informe diario de LibrosPE</h3>
    <p>Periodo: {r['desde'].strftime('%d/%m/%Y %H:%M')} → {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
    <ul>
      <li><b>Ventas (24 h):</b> {r['n_ventas']} — S/ {r['total_ventas']:.2f}
          ({r['boletas']} boletas, {r['facturas']} facturas)</li>
      <li><b>Pedidos nuevos (24 h):</b> {r['pedidos_nuevos']}
          ({r['pedidos_pendientes']} pendientes de atención)</li>
      <li><b>Stock bajo:</b> {len(r['bajos'])} producto(s)</li>
      <li><b>Conteos con ajuste pendiente:</b> {r['ajustes_pendientes']}</li>
    </ul>
    {caja_html}
    <h4>Productos con stock bajo</h4>
    <ul>{lineas_bajo}</ul>
    <p style="color:#888;font-size:12px;">Generado automáticamente por LibrosPE.</p>
    """


def main():
    probar = "--probar" in sys.argv
    with app.app_context():
        r = _resumen_24h()
        html = _html(r)
        asunto = (f"📊 Informe diario LibrosPE — {r['n_ventas']} ventas "
                  f"S/ {r['total_ventas']:.2f} — {len(r['bajos'])} con stock bajo")
        if probar:
            print(asunto)
            print(html)
            return 0
        admins = UsuarioSistema.query.filter_by(rol="administrador").all()
        destinatarios = [a.correo for a in admins if a.correo]
        if not destinatarios:
            print("⚠️ Sin administradores con correo: no hay a quien enviar el informe")
            return 1
        _enviar_correo_html(asunto, html, destinatarios)
        print(f"✅ Informe enviado a {len(destinatarios)} destinatario(s): "
              f"{', '.join(destinatarios)}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
