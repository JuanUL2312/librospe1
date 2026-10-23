"""Prueba funcional del API Gateway JWT (sin tocar BD de producción)."""
import json
import os
import sys

sys.path.insert(0, r"C:\Users\Administrador\Documents\GitHub\librospe1\Micrososervicios\www")

os.environ["SECRET_KEY"] = "clave-de-prueba-para-el-smoke-test"
os.environ["MS_VENTAS_URL"] = "http://127.0.0.1:59999"    # puerto muerto
os.environ["MS_USUARIOS_URL"] = "http://127.0.0.1:59999"   # puerto muerto
os.environ["SERVICE_TOKEN"] = "token-interno-de-prueba"

from app_api import crear_app
from jwt_auth import crear_token

app = crear_app()
app.config["TESTING"] = True
c = app.test_client()

fallos = []

def comprobar(nombre, condicion, detalle=""):
    estado = "OK " if condicion else "FALLO"
    print(f"[{estado}] {nombre} {detalle}")
    if not condicion:
        fallos.append(nombre)

# 1) Salud local
r = c.get("/api/health")
comprobar("GET /api/health -> 200", r.status_code == 200, str(r.status_code))

# 2) POST API sin Authorization -> 403 (CSRF-API)
r = c.post("/api/v1/ventas/crear", json={"producto_id": 1})
comprobar("POST sin JWT -> 403", r.status_code == 403, str(r.status_code))

# 3) Bearer corrupto -> 401
r = c.post("/api/v1/ventas/crear", json={"producto_id": 1},
           headers={"Authorization": "Bearer basura.basura.basura"})
comprobar("Bearer inválido -> 401", r.status_code == 401, str(r.status_code))

# 4) Token válido pero servicio caído -> 503 con JSON en español
with app.app_context():
    token, _ = crear_token(7, "vendedor", correo="v@x.com", nombre="Vendedor")
r = c.post("/api/v1/ventas/crear",
           json={"producto_id": 1, "cantidad": 2},
           headers={"Authorization": f"Bearer {token}"})
cuerpo = r.get_json() or {}
comprobar("Servicio caído -> 503", r.status_code == 503, str(r.status_code))
comprobar("503 con detalle en español",
          "no disponible" in cuerpo.get("error", ""), cuerpo.get("error", ""))

# 5) Payload inválido -> 400 antes de contactar al servicio
r = c.post("/api/v1/ventas/crear", json={"producto_id": 1, "cantidad": 0},
           headers={"Authorization": f"Bearer {token}"})
comprobar("cantidad=0 -> 400", r.status_code == 400, str(r.status_code))

# 6) listar exige rol admin/vendedor: un cliente recibe 403
with app.app_context():
    token_cliente, _ = crear_token(9, "cliente", correo="c@x.com")
r = c.get("/api/v1/ventas/listar", headers={"Authorization": f"Bearer {token_cliente}"})
comprobar("Cliente sin rol -> 403", r.status_code == 403, str(r.status_code))

# 7) Login con servicio de usuarios caído -> 503
r = c.post("/api/v1/auth/login", json={"correo": "a@b.com", "clave": "x"})
comprobar("Login sin servicio -> 503", r.status_code == 503, str(r.status_code))

# 8) Token expirado -> 401 con mensaje claro
import jwt as pyjwt
from datetime import datetime, timedelta, timezone
vencido = pyjwt.encode(
    {"sub": "1", "rol": "admin", "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
     "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
     "jti": "x", "typ": "access"},
    os.environ["SECRET_KEY"], algorithm="HS256")
r = c.get("/api/v1/ventas/listar", headers={"Authorization": f"Bearer {vencido}"})
comprobar("Token expirado -> 401", r.status_code == 401, str(r.status_code))

# 9) Ruta inexistente -> 404 JSON
r = c.get("/api/v1/no-existe")
comprobar("404 en JSON", r.status_code == 404 and "error" in (r.get_json() or {}))

# ---------- INVENTARIO ----------
with app.app_context():
    tok_admin, _ = crear_token(1, "admin", correo="a@x.com", nombre="Admin")
    tok_vend, _ = crear_token(2, "vendedor", correo="v@x.com")
r = c.get("/api/v1/inventario/productos",
          headers={"Authorization": f"Bearer {tok_admin}"})
comprobar("Inventario caído -> 503", r.status_code == 503, str(r.status_code))
r = c.post("/api/v1/inventario/productos",
           json={"nombre": "X", "cantidad": 1, "precio": 10},
           headers={"Authorization": f"Bearer {tok_vend}"})
comprobar("Crear producto sin rol admin -> 403", r.status_code == 403, str(r.status_code))
r = c.post("/api/v1/inventario/productos", json={"nombre": "X"},
           headers={"Authorization": f"Bearer {tok_admin}"})
comprobar("Producto sin precio -> 400", r.status_code == 400, str(r.status_code))
r = c.put("/api/v1/inventario/stock/1", json={},
          headers={"Authorization": f"Bearer {tok_vend}"})
comprobar("Stock sin cantidad -> 400", r.status_code == 400, str(r.status_code))
r = c.put("/api/v1/inventario/stock/1", json={"cantidad": -1},
          headers={"Authorization": f"Bearer {tok_vend}"})
comprobar("Stock negativo -> 400", r.status_code == 400, str(r.status_code))

# ---------- USUARIOS ----------
r = c.get("/api/v1/usuarios/listar", headers={"Authorization": f"Bearer {tok_vend}"})
comprobar("Listar usuarios con rol vendedor -> 403", r.status_code == 403, str(r.status_code))
r = c.post("/api/v1/usuarios/crear",
           json={"correo": "n@x.com", "nombres": "N", "apellidos": "A", "clave": "123456"},
           headers={"Authorization": f"Bearer {tok_admin}"})
comprobar("Usuarios caído (alta válida) -> 503", r.status_code == 503, str(r.status_code))
r = c.post("/api/v1/usuarios/crear", json={"correo": "malo"},
           headers={"Authorization": f"Bearer {tok_admin}"})
comprobar("Alta sin nombres -> 400", r.status_code == 400, str(r.status_code))

# ---------- CLIENTES ----------
r = c.post("/api/v1/clientes/registro", json={})
comprobar("Registro público sin datos -> 400 (no 403 CSRF)",
          r.status_code == 400, str(r.status_code))
r = c.post("/api/v1/clientes/registro",
           json={"email": "n@x.com", "nombres": "N", "apellidos": "A",
                 "clave": "secreta123", "departamento": "Junin",
                 "provincia": "Huancayo", "distrito": "Chilca"})
comprobar("Registro con datos y servicios caídos -> 503",
          r.status_code == 503, str(r.status_code))
r = c.get("/api/v1/clientes/5", headers={"Authorization": f"Bearer {token_cliente}"})
comprobar("Cliente (id 9) ve cliente ajeno (5) -> 403",
          r.status_code == 403, str(r.status_code))
r = c.get("/api/v1/clientes/9", headers={"Authorization": f"Bearer {token_cliente}"})
comprobar("Cliente ve SU registro pero servicio caído -> 503",
          r.status_code == 503, str(r.status_code))
r = c.put("/api/v1/clientes/9", json={"estado": 0},
          headers={"Authorization": f"Bearer {token_cliente}"})
comprobar("Cliente no se auto-deshabilita -> 400", r.status_code == 400, str(r.status_code))
r = c.delete("/api/v1/clientes/9", headers={"Authorization": f"Bearer {token_cliente}"})
comprobar("Cliente no borra -> 403", r.status_code == 403, str(r.status_code))
r = c.put("/api/v1/clientes/9", json={"telefono": "999"},
          headers={"Authorization": f"Bearer {token_cliente}"})
comprobar("Cliente edita SU teléfono (servicio caído) -> 503",
          r.status_code == 503, str(r.status_code))

# ---------- RUTAS EXENTAS DE JWT ----------
r = c.put("/api/v1/clientes/9", json={"telefono": "1"})
comprobar("PUT sin JWT -> 403 (CSRF-API)", r.status_code == 403, str(r.status_code))

# 10) Auditoría local escrita
ruta_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "www", "logs",
                        "auditoria_api.log")
existe = os.path.exists(ruta_log)
lineas = 0
if existe:
    with open(ruta_log, encoding="utf-8") as f:
        lineas = len(f.readlines())
comprobar("Log de auditoría con eventos", existe and lineas > 0, f"({lineas} líneas)")

print()
print("TOTAL:", "TODO OK" if not fallos else f"{len(fallos)} FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
