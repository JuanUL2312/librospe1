import sys, shutil, zipfile, os, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)

SRC = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_fixed.xlsx"
TMP = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_ms2_extract"
OUT = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_hybrid_ms.xlsx"

def q(tag): return f"{{{NS}}}{tag}"

if os.path.exists(TMP): shutil.rmtree(TMP)
with zipfile.ZipFile(SRC) as z:
    z.extractall(TMP)

def load(path):
    t = ET.ElementTree(); t.parse(path); return t

def set_inline(c, value):
    for child in list(c):
        c.remove(child)
    c.set("t", "inlineStr")
    is_ = ET.SubElement(c, q("is"))
    tt = ET.SubElement(is_, q("t"))
    tt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    tt.text = value

def clear_cell(c):
    for child in list(c):
        c.remove(child)

def make_cell(ref, s, kind, val):
    c = ET.Element(q("c")); c.set("r", ref); c.set("s", s)
    if kind == "inlineStr":
        set_inline(c, val)
    else:
        v = ET.SubElement(c, q("v")); v.text = val
    return c

def num_s(v):
    return str(int(v)) if float(v) == int(v) else str(v)

# ================= sheet3: HU-16 en fila 19 =================
p3 = os.path.join(TMP, "xl", "worksheets", "sheet3.xml")
t = load(p3); root = t.getroot(); sd = root.find(q("sheetData"))
rows = {int(r.get("r")): r for r in sd.findall(q("row"))}
r19 = rows[19]
map3 = {"B19": ("47","inlineStr","HU-16"),
        "C19": ("47","inlineStr","Como administrador, quiero exponer los microservicios de comercial, inventario y monitor como API REST para consultar pedidos, productos y su estado."),
        "D19": ("47","inlineStr","Microservicios"),
        "E19": ("57","inlineStr","EN PLANIFICACIÓN"),
        "F19": ("47","num","16.0"),
        "G19": ("47","inlineStr","Sprint 4"),
        "H19": ("47","num","200.0"),
        "I19": ("47","inlineStr","Alta - APIs REST de microservicios con tablas espejo y monitoreo")}
for c in r19:
    if c.get("r") in map3:
        s, kind, val = map3[c.get("r")]
        clear_cell(c); c.set("s", s)
        if kind == "inlineStr":
            set_inline(c, val)
        else:
            v = ET.SubElement(c, q("v")); v.text = val
t.write(p3, encoding="UTF-8", xml_declaration=True)
print("sheet3 OK: HU-16 -> fila 19")

# ================= sheet4: 5 criterios HU-16 (sobrescribir filas 77-81) =================
p4 = os.path.join(TMP, "xl", "worksheets", "sheet4.xml")
t = load(p4); root = t.getroot(); sd = root.find(q("sheetData"))
rows = {int(r.get("r")): r for r in sd.findall(q("row"))}
criterios = [
    ("Diseñar microservicio comercial con endpoints de pedidos y ventas", "Tablas espejo para sincronizar el módulo comercial con los microservicios."),
    ("Diseñar microservicio inventario con endpoints de productos y stock", "Validar el stock en tiempo real desde el servicio de inventario."),
    ("Implementar monitor de servicios con health check (/api/health)", "Mostrar el estado de los microservicios en un dashboard."),
    ("Configurar la sincronización de tablas espejo entre módulos y microservicios", "Sincronizar pedidos, productos y proveedores de forma automática."),
    ("Proteger las APIs REST con roles de acceso (admin y vendedor)", "Solo usuarios autenticados con rol autorizado pueden consumir los endpoints."),
]
for rn, (crit, com) in zip(range(77, 82), criterios):
    row = rows.get(rn)
    if row is None:
        row = ET.Element(q("row")); row.set("r", str(rn))
        sd.append(row); rows[rn] = row
    for ex in list(row):
        row.remove(ex)
    for col, val in [("B","HU-16"), ("C",crit), ("D",com)]:
        row.append(make_cell(f"{col}{rn}", "16", "inlineStr", val))
t.write(p4, encoding="UTF-8", xml_declaration=True)
print("sheet4 OK: 5 criterios HU-16 -> filas 77-81")

# ================= sheet5: 4 tareas H11 (filas 33-36) + TOTAL fila 37 =================
p5 = os.path.join(TMP, "xl", "worksheets", "sheet5.xml")
t = load(p5); root = t.getroot(); sd = root.find(q("sheetData"))
rows = {int(r.get("r")): r for r in sd.findall(q("row"))}
tareas_h11 = [
    ("Implementar microservicio comercial (pedidos, ventas) con tablas espejo", "Uchuypoma Lanazca Juan Victor", 2.0),
    ("Implementar microservicio inventario (productos, stock) con tablas espejo", "Villar Ureta Adiel Riko Felipe", 2.0),
    ("Implementar microservicio monitor (/api/health) y dashboard de estado", "Uchuypoma Lanazca Juan Victor", 2.0),
    ("Desplegar microservicios y verificar endpoints REST en producción", "Villar Ureta Adiel Riko Felipe", 2.0),
]
for rn, (ta, resp, hr) in zip(range(33, 37), tareas_h11):
    row = rows.get(rn)
    if row is None:
        row = ET.Element(q("row")); row.set("r", str(rn))
        sd.append(row); rows[rn] = row
    for ex in list(row):
        row.remove(ex)
    for col, val, sty in [("A","H11","65"), ("B",ta,"65"), ("C",resp,"65")]:
        row.append(make_cell(f"{col}{rn}", sty, "inlineStr", val))
    row.append(make_cell(f"D{rn}", "66", "num", num_s(hr)))
# TOTAL fila 37
row = rows.get(37)
if row is None:
    row = ET.Element(q("row")); row.set("r", "37")
    sd.append(row); rows[37] = row
for ex in list(row):
    row.remove(ex)
cA = make_cell("A37", "68", "inlineStr", "TOTAL")
row.append(cA)
cD = ET.Element(q("c")); cD.set("r", "D37"); cD.set("s", "68")
f = ET.SubElement(cD, q("f")); f.text = "SUM(D3:D36)"
v = ET.SubElement(cD, q("v")); v.text = "108.0"
row.append(cD)
t.write(p5, encoding="UTF-8", xml_declaration=True)
print("sheet5 OK: 4 tareas H11 (33-36) + TOTAL fila 37 (SUM D3:D36=108)")

# ================= sheet13: H10 (fila 20) + spacer 21; desplazar filas 20-30 -> 22-32 =================
p13 = os.path.join(TMP, "xl", "worksheets", "sheet13.xml")
t = load(p13); root = t.getroot(); sd = root.find(q("sheetData"))
rows = {int(r.get("r")): r for r in sd.findall(q("row"))}

# 1) eliminar filas >= 20 (las desplazaremos con nuevos numeros)
to_move = {}
for rn in sorted(r for r in rows if r >= 20):
    to_move[rn] = rows[rn]; sd.remove(rows[rn])

# 2) re-numerar filas 20-30 -> 22-32 (identificador interno)
renum = {rn: rn + 2 for rn in to_move}
for old, el in to_move.items():
    newrn = renum[old]
    el.set("r", str(newrn))
    for c in el:
        ref = c.get("r")
        if ref:
            c.set("r", re.sub(r"(\d+)$", str(newrn), ref))
    sd.append(el)

# 3) ajustar formulas/caches en filas desplazadas
for rn in (22, 26, 27):
    el = None
    for r in sd.findall(q("row")):
        if int(r.get("r")) == rn:
            el = r; break
    if el is None: continue
    for c in el:
        ref = c.get("r")
        if rn == 22 and ref == "E22":
            f = c.find(q("f")); v = c.find(q("v"))
            if f is None: f = ET.SubElement(c, q("f"))
            f.text = "SUM(E2:E20)"
            if v is None: v = ET.SubElement(c, q("v"))
            v.text = "180"
        if rn == 26 and ref == "E26":
            f = c.find(q("f")); v = c.find(q("v"))
            if f is None: f = ET.SubElement(c, q("f"))
            f.text = "E24*E25"
            if v is None: v = ET.SubElement(c, q("v"))
            v.text = "8"
        if rn == 27 and ref == "E27":
            vv = c.find(q("v"))
            if vv is None: vv = ET.SubElement(c, q("v"))
            vv.text = "22.5"

# 4) insertar fila 20 (H10) y fila 21 (spacer) antes de la fila 22
idx22 = None
for i, r in enumerate(sd.findall(q("row"))):
    if int(r.get("r")) == 22:
        idx22 = i; break
hist_styles = {"A":"140", "B":"137", "C":"137", "D":"138", "E":"139"}
rowh = ET.Element(q("row")); rowh.set("r", "20")
vals = {"A": ("H10", "inlineStr"), "B": ("10.0", "num"),
        "C": ("01 MUY ALTA", "inlineStr"),
        "D": ("Como administrador, quiero que el sistema exponga los microservicios de comercial, inventario y monitor como API REST para consultar pedidos, productos y su estado.", "inlineStr"),
        "E": ("16.0", "num")}
for col in "ABCDE":
    val, kind = vals[col]
    c = ET.SubElement(rowh, q("c")); c.set("r", f"{col}20"); c.set("s", hist_styles[col])
    if kind == "inlineStr":
        set_inline(c, val)
    else:
        v = ET.SubElement(c, q("v")); v.text = val
for col in "FGHIJKLMNOPQRSTUVWXYZ":
    c = ET.SubElement(rowh, q("c")); c.set("r", f"{col}20"); c.set("s", "64")
rows21 = ET.Element(q("row")); rows21.set("r", "21")
for col in "ABCDE":
    c = ET.SubElement(rows21, q("c")); c.set("r", f"{col}21"); c.set("s", "135")
sd.insert(idx22 if idx22 is not None else 0, rowh)
sd.insert((idx22 if idx22 is not None else 0) + 1, rows21)

# 5) merges + dataValidation
mx = root.find(q("mergeCells"))
if mx is not None:
    for mr in ["A20:A21","B20:B21","C20:C21","D20:D21","E20:E21"]:
        e = ET.SubElement(mx, q("mergeCell")); e.set("ref", mr)
dv = root.find(q("dataValidations"))
if dv is not None:
    for d in dv.findall(q("dataValidation")):
        sq = d.get("sqref")
        if sq and "C20" not in sq:
            d.set("sqref", sq + " C20")

t.write(p13, encoding="UTF-8", xml_declaration=True)
print("sheet13 OK: H10 (fila 20), TOTAL 180, dias 22.5")

# ================= rezip (OUT fuera de TMP) =================
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