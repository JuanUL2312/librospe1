import sys, shutil, zipfile, os, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_intro.xlsx"
TMP = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_est_extract"
OUT = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\scrum_est.xlsx"

if os.path.exists(TMP): shutil.rmtree(TMP)
with zipfile.ZipFile(SRC) as z:
    z.extractall(TMP)

p = os.path.join(TMP, "xl", "worksheets", "sheet13.xml")
x = open(p, encoding="utf-8").read()

def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ===== 1) extraer filas 1..21 existentes =====
rows_keep = []
for rn in range(1, 22):
    m = re.search(rf'<row r="{rn}"[^>]*>.*?</row>', x, re.S)
    if m: rows_keep.append(m.group(0))
    else: raise SystemExit(f"falta row {rn}")

# ===== 2) nuevas filas de datos H11..H19 (pares) + spacers (impares) =====
def cell(ref, s, body=""):
    if body is None: return f'<c r="{ref}" s="{s}" />'
    return f'<c r="{ref}" s="{s}"{body}</c>'

def data_row(n, num, hid, prio, desc, est):
    r = n
    A = f'<c r="A{r}" s="131" t="inlineStr"><is><t xml:space="preserve">{esc(hid)}</t></is></c>'
    B = f'<c r="B{r}" s="137"><v>{num}</v></c>'
    C = f'<c r="C{r}" s="137" t="inlineStr"><is><t xml:space="preserve">{esc(prio)}</t></is></c>'
    D = f'<c r="D{r}" s="138" t="inlineStr"><is><t xml:space="preserve">{esc(desc)}</t></is></c>'
    E = f'<c r="E{r}" s="139"><v>{est}</v></c>'
    return f'<row r="{r}">{A}{B}{C}{D}{E}</row>'

def spacer_row(n):
    return (f'<row r="{n}"><c r="A{n}" s="135" /><c r="B{n}" s="135" /><c r="C{n}" s="135" />'
            f'<c r="D{n}" s="135" /><c r="E{n}" s="135" /></row>')

nuevas = [
    ("H11", "01 MUY ALTA", "Como cliente, quiero ver el catálogo de productos para conocer los artículos disponibles antes de comprar.", 24),
    ("H12", "01 MUY ALTA", "Como cliente, quiero seleccionar productos y generar mi pedido en el sistema para agilizar mi atención en el local.", 24),
    ("H13", "01 MUY ALTA", "Como administrador, quiero recibir una notificación en tiempo real cuando un cliente llegue al local, para reducir el tiempo de espera en la atención.", 16),
    ("H14", "03 MEDIA", "Como administrador, quiero realizar copias de respaldo de la base de datos para evitar pérdida de información.", 8),
    ("H15", "03 MEDIA", "Como cliente, quiero recuperar mi contraseña para volver a acceder al sistema si la olvido.", 8),
    ("H16", "03 MEDIA", "Como vendedor, quiero consultar el historial de ventas por período para revisar mi desempeño.", 16),
    ("H17", "01 MUY ALTA", "Como administrador, quiero gestionar las devoluciones de productos para mantener la satisfacción del cliente.", 16),
    ("H18", "01 MUY ALTA", "Como vendedor, quiero realizar el seguimiento de los pedidos por estado y confirmar la entrega para informar al cliente sobre su compra.", 16),
    ("H19", "03 MEDIA", "Como cliente, quiero calificar y comentar los productos que compré para compartir mi experiencia.", 8),
]

n = 20  # última fila de dato existente (H10), liena 21 = spacer
for i, (hid, prio, desc, est) in enumerate(nuevas):
    dr = 22 + 2 * i      # 22,24,26,...,38
    sr = dr + 1          # 23,25,27,...,39
    rows_keep.append(data_row(dr, 11 + i, hid, prio, desc, est))
    rows_keep.append(spacer_row(sr))
ultimo_dato = 38  # última fila de dato (H19)
total_row = 40

# ===== 3) TOTAL + bloque inferior renumerado =====
total_row = ultimo_dato + 2  # 40
rows_keep.append(f'<row r="{total_row}"><c r="D{total_row}" s="78" t="s"><v>308</v></c>'
                 f'<c r="E{total_row}" s="141"><f>SUM(E2:E{ultimo_dato})</f><v>316</v></c></row>')
r = total_row + 1  # 41
rows_keep.append(f'<row r="{r}"><c r="E{r}" s="142" /></row>')
r = total_row + 2  # 42
rows_keep.append(f'<row r="{r}"><c r="D{r}" s="78" t="s"><v>310</v></c><c r="E{r}" s="141"><v>4.0</v></c></row>')
r = total_row + 3  # 43
rows_keep.append(f'<row r="{r}" ht="15.75" customHeight="1"><c r="D{r}" s="78" t="s"><v>312</v></c>'
                 f'<c r="E{r}" s="143"><v>2.0</v></c></row>')
r = total_row + 4  # 44
rows_keep.append(f'<row r="{r}" ht="15.75" customHeight="1"><c r="D{r}" s="78" t="s"><v>314</v></c>'
                 f'<c r="E{r}" s="143"><f>E{r-2}*E{r-1}</f><v>8</v></c></row>')
r = total_row + 5  # 45
rows_keep.append(f'<row r="{r}" ht="15.75" customHeight="1"><c r="D{r}" s="78" t="s"><v>316</v></c>'
                 f'<c r="E{r}" s="143"><f>E{total_row}/E{r-1}</f><v>39.5</v></c></row>')
r = total_row + 6  # 46..49 spacers
for k in range(4):
    rows_keep.append(f'<row r="{r}" ht="15.75" customHeight="1" />')
    r += 1
# "<" en fila 50
fil_izq = r  # 50
rows_keep.append(f'<row r="{fil_izq}" ht="15.75" customHeight="1"><c r="D{fil_izq}" s="27" t="s"><v>372</v></c></row>')

# ===== 4) reemplazar sheetData =====
start = x.index("<sheetData>")
end = x.index("</sheetData>") + len("</sheetData>")
x2 = x[:start] + "<sheetData>" + "".join(rows_keep) + "</sheetData>" + x[end:]

# ===== 5) dataValidation -> C2..C38 =====
sq = " ".join(f"C{i}" for i in range(2, 39, 2))
x2 = re.sub(r'sqref="[^"]*"', f'sqref="{sq}"', x2)

open(p, "w", encoding="utf-8").write(x2)
print("sheet13 OK: 19 historias, TOTAL fila", total_row, "=SUM(E2:E38) ->", ultimo_dato)

# ===== rezip =====
if os.path.exists(OUT): os.remove(OUT)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, dn, fn in os.walk(TMP):
        if dp == os.path.dirname(OUT): continue
        for f in fn:
            full = os.path.join(dp, f)
            arc = os.path.relpath(full, TMP).replace("\\", "/")
            z.write(full, arc)
print("escrito:", OUT, os.path.getsize(OUT), "bytes")