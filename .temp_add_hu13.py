import sys, shutil, zipfile, os, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)

SRC = r"C:\Users\Administrador\Documents\GitHub\librospe1\_PLANTILLA SCRUM.xlsx"
TMP = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_ms3_extract"
OUT = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_hybrid_ms2.xlsx"

def q(tag): return f"{{{NS}}}{tag}"

if os.path.exists(TMP): shutil.rmtree(TMP)
with zipfile.ZipFile(SRC) as z:
    z.extractall(TMP)

def set_inline(c, value):
    for child in list(c):
        c.remove(child)
    c.set("t", "inlineStr")
    is_ = ET.SubElement(c, q("is"))
    tt = ET.SubElement(is_, q("t"))
    tt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    tt.text = value

# ============ sheet3: insertar HU-13 (fila 16) y HU-14 (fila 17) ============
p3 = os.path.join(TMP, "xl", "worksheets", "sheet3.xml")
t = ET.ElementTree(); t.parse(p3); root = t.getroot(); sd = root.find(q("sheetData"))

# renumeración NO necesaria: las filas 16-17 no existían, insertamos antes de la fila 18
def build_hu(rn, hid, c, mod, estado, esfuerzo, sprint, prio, comentario):
    row = ET.Element(q("row")); row.set("r", str(rn))
    cmap = {"B": (hid, "inlineStr", "47"), "C": (c, "inlineStr", "47"),
            "D": (mod, "inlineStr", "47")}
    for col, (val, kind, sty) in cmap.items():
        cel = ET.SubElement(row, q("c")); cel.set("r", f"{col}{rn}"); cel.set("s", sty)
        set_inline(cel, val)
    e = ET.SubElement(row, q("c")); e.set("r", f"E{rn}"); e.set("s", "57"); set_inline(e, estado)
    f = ET.SubElement(row, q("c")); f.set("r", f"F{rn}"); f.set("s", "47")
    v = ET.SubElement(f, q("v")); v.text = esfuerzo
    g = ET.SubElement(row, q("c")); g.set("r", f"G{rn}"); g.set("s", "47"); set_inline(g, sprint)
    h = ET.SubElement(row, q("c")); h.set("r", f"H{rn}"); h.set("s", "47")
    v = ET.SubElement(h, q("v")); v.text = prio
    i = ET.SubElement(row, q("c")); i.set("r", f"I{rn}"); i.set("s", "47"); set_inline(i, comentario)
    for col in "JKLMNOPQRSTUVWXYZ":
        cel = ET.SubElement(row, q("c")); cel.set("r", f"{col}{rn}"); cel.set("s", "1")
    return row

row13 = build_hu(16, "HU-13",
    "Como administrador, quiero registrar y gestionar los proveedores para mantener actualizado el abastecimiento y la relación con los abastecedores.",
    "Compras", "Pendiente", "16.0", "Sprint 4", "200.0",
    "Alta - CRUD de proveedores con consulta de RUC y reporte de productos por proveedor")
row14 = build_hu(17, "HU-14",
    "Como vendedor, quiero realizar el seguimiento de los pedidos por estado y confirmar la entrega para informar al cliente sobre su compra.",
    "Ventas", "Pendiente", "16.0", "Sprint 4", "200.0",
    "Alta - Máquina de estados de pedidos, confirmación de recepción y comprobante de venta")

# insertar filas 16,17 antes de la fila 18
idx = None
for i, r in enumerate(sd.findall(q("row"))):
    if int(r.get("r")) == 18:
        idx = i; break
if idx is None:
    sd.append(row13); sd.append(row14)
else:
    sd.insert(idx, row13); sd.insert(idx + 1, row14)

# reordenar numericamente
allrows = sd.findall(q("row"))
sd[:] = []
for r in sorted(allrows, key=lambda x: int(x.get("r"))):
    sd.append(r)

t.write(p3, encoding="UTF-8", xml_declaration=True)
print("sheet3 OK: HU-13/HU-14 insertadas en filas 16/17")

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