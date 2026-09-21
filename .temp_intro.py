import sys, shutil, zipfile, os, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)

SRC = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_hybrid_ms2.xlsx"
TMP = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_intro_extract"
OUT = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_intro.xlsx"

def q(tag): return f"{{{NS}}}{tag}"

if os.path.exists(TMP): shutil.rmtree(TMP)
with zipfile.ZipFile(SRC) as z:
    z.extractall(TMP)

p = os.path.join(TMP, "xl", "sharedStrings.xml")
t = ET.ElementTree(); t.parse(p); root = t.getroot()
sis = root.findall(q("si"))

def set_plain(si, text):
    for ch in list(si):
        si.remove(ch)
    t_el = ET.SubElement(si, q("t"))
    t_el.text = text

reemplazos = {
 67: "La Librería Salesiana de Don Bosco Huancayo ofrece libros de texto, novelas, diccionarios, materiales religiosos y útiles escolares para estudiantes y docentes. Su venta se realiza hoy en línea y en el punto de venta (POS) de la caja, con entrega a domicilio y comprobantes electrónicos.",
 94: "Desarrollar un sistema web para la venta en línea y presencial de la Librería Don Bosco Huancayo que optimice los procesos de comercialización, controle el inventario en tiempo real, gestione pedidos con seguimiento y entrega a domicilio, y emita comprobantes de pago, ampliando su alcance a nuevos clientes y mejorando la atención al cliente mediante herramientas digitales modernas y seguras.",
 126: "El sistema debe ser compatible con múltiples dispositivos (PC, tablet y celular) y mostrar las imágenes de los productos para captar la atención del cliente.",
 133: "El sistema debe permitir al administrador registrar, actualizar y eliminar productos (libros, artículos, accesorios, etc.) manteniendo un catálogo actualizado.",
 141: "El sistema debe controlar el stock de productos disponibles y actualizarlo automáticamente con cada venta realizada en línea o en caja.",
 149: "El sistema debe permitir registrar ventas en línea (carrito) y presenciales (POS de caja), con cálculo del total, descuentos y vuelto.",
 158: "El sistema debe permitir generar reportes de ventas e inventario por período con filtros y exportación a PDF y Excel.",
 166: "El sistema debe gestionar pedidos con estados (pendiente, confirmado, entregado, cancelado) y la confirmación de entrega a domicilio por el cliente.",
 175: "El sistema debe permitir el acceso mediante usuario y contraseña con niveles de permisos por rol (administrador, vendedor y cliente).",
 181: "El sistema debe exponer microservicios de comercial, inventario y monitoreo (health check) como API REST, con tablas espejo sincronizadas.",
 189: "El sistema debe registrar la auditoría de acciones, bloquear intentos de acceso fallidos y proteger las rutas según los permisos del rol.",
}

for idx, text in reemplazos.items():
    if 0 <= idx < len(sis):
        set_plain(sis[idx], text)
    else:
        print("ERROR idx fuera de rango:", idx)

t.write(p, encoding="UTF-8", xml_declaration=True)
print("sharedStrings OK: descripcion/objetivo/9 requerimientos actualizados")

# ============ rezip ============
if os.path.exists(OUT): os.remove(OUT)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, dn, fn in os.walk(TMP):
        if dp == os.path.dirname(OUT):
            continue
        for f in fn:
            full = os.path.join(dp, f)
            arc = os.path.relpath(full, TMP).replace("\\", "/")
            z.write(full, arc)
print("escrito:", OUT, os.path.getsize(OUT), "bytes")