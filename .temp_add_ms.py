import sys, re, shutil, zipfile, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_XML = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("", NS)

SRC = r"C:\Users\Administrador\Documents\GitHub\librospe1\Cronograma_112_tareas_Don_Bosco.xlsx"
TMP = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\crono_ms"
OUT = r"C:\Users\Administrador\Documents\GitHub\librospe1\Cronograma_112_tareas_Don_Bosco.xlsx"

def q(tag): return f"{{{NS}}}{tag}"

# ---------- extraer ----------
if os.path.exists(TMP): shutil.rmtree(TMP)
with zipfile.ZipFile(SRC) as z:
    z.extractall(TMP)

spath = os.path.join(TMP, "xl", "worksheets", "sheet1.xml")
tree = ET.ElementTree(); tree.parse(spath)
root = tree.getroot()
sd = root.find(q("sheetData"))

# ---------- nuevas tareas microservicios (dentro de Sprint 4, rango 7/26-9/1) ----------
MS = [
    ("3.4.26", "Diseñar la arquitectura de microservicios (comercial, inventario, monitor) con blueprints Flask independientes", "8/25/26", "8/26/26", "JL"),
    ("3.4.27", "Implementar microservicio comercial (pedidos y ventas) con tablas espejo", "8/25/26", "8/28/26", "AU (Adiel Riko Felipe)"),
    ("3.4.28", "Implementar microservicio inventario (productos y stock con alerta de stock bajo) con tablas espejo", "8/25/26", "8/28/26", "JL"),
    ("3.4.29", "Implementar microservicio monitor (/api/health) y dashboard de estado de servicios", "8/29/26", "8/30/26", "AU (Adiel Riko Felipe)"),
    ("3.4.30", "Configurar la sincronización de las tablas espejo (pedidos, productos y proveedores) entre módulos y microservicios", "8/29/26", "8/31/26", "JL"),
    ("3.4.31", "Probar los endpoints REST y desplegar los microservicios en el entorno de producción", "8/31/26", "9/1/26", "AU (Adiel Riko Felipe)"),
]

def make_row(cid, tarea, ini, fin, pers, rn):
    el = ET.Element(q("row"))
    el.set("r", str(rn))
    data = [("A", "3", "3. Desarrollo"), ("B", "3", "Sprint 4"), ("C", "3", cid),
            ("D", "4", tarea), ("E", "3", ini), ("F", "3", fin), ("G", "3", pers)]
    for col, s, val in data:
        c = ET.SubElement(el, q("c"))
        c.set("r", f"{col}{rn}")
        c.set("s", s)
        c.set("t", "inlineStr")
        is_ = ET.SubElement(c, q("is"))
        t = ET.SubElement(is_, q("t"))
        t.set(f"{{{NS_XML}}}space", "preserve")
        t.text = val
    return el

n_add = len(MS)
insert_after = 90  # fila 90 = 3.4.25 (Sprint 4)

# ---------- actualizar Fin de Mantenimiento (fila fila 113.. -> Fin 7/31/27 a 4/30/27) ----------
def find_fin_cell(row):
    for c in row:
        if c.get("r", "").startswith("F"):
            return c
    return None

for row in sd.findall(q("row")):
    cid_el = None
    for c in row:
        if c.get("r", "").startswith("C"):
            cid_el = c
            break
    if cid_el is None:
        continue
    id_txt = "".join(x.text or "" for x in cid_el.iter(q("t")))
    if id_txt.startswith("6."):
        fin = find_fin_cell(row)
        if fin is not None:
            for t in fin.iter(q("t")):
                if t.text == "7/31/27":
                    t.text = "4/30/27"
                    print("   Mantenimiento", id_txt, "-> Fin 4/30/27")

# ---------- renumerar filas > 90 (empujar hacia abajo) ----------
for row in sd.findall(q("row")):
    r = int(row.get("r"))
    if r > insert_after:
        nr = r + n_add
        row.set("r", str(nr))
        for c in row:
            ref = c.get("r")
            if ref:
                c.set("r", re.sub(r"(\d+)$", str(nr), ref))

# ---------- insertar las 6 nuevas filas en orden (91..96) ----------
rows = sd.findall(q("row"))
# localizar indice donde empieza r==97 (primera renumerada)
idx = None
for i, row in enumerate(rows):
    if int(row.get("r")) == insert_after + 1 + n_add:
        idx = i
        break
if idx is None:
    for i, row in enumerate(rows):
        if int(row.get("r")) > insert_after + n_add:
            idx = i
            break
new_els = [make_row(cid, tarea, ini, fin, pers, insert_after + 1 + i)
           for i, (cid, tarea, ini, fin, pers) in enumerate(MS)]
if idx is not None:
    for k, el in enumerate(new_els):
        sd.insert(idx + k, el)
else:
    sd.extend(new_els)

tree.write(spath, encoding="UTF-8", xml_declaration=True)
print("sheet1.xml actualizado: 6 tareas microservicios insertadas + Fin Mantenimiento 4/30/27")

# ---------- rezippear ----------
if os.path.exists(OUT): os.remove(OUT)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, dn, fn in os.walk(TMP):
        for f in fn:
            full = os.path.join(dp, f)
            arc = os.path.relpath(full, TMP).replace("\\", "/")
            z.write(full, arc)
print("escrito:", OUT, os.path.getsize(OUT), "bytes")