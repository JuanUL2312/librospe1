import os
import sys
import time
import hmac
import json
from pathlib import Path
from urllib.parse import quote, quote_plus
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from flask import Flask, abort, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, text, or_
from sqlalchemy.exc import IntegrityError

# Paquete de microservicios (blueprints independientes: comercial, inventario, monitor)
from microservicios import register_microservicios
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Asegurar salida UTF-8 (evita UnicodeEncodeError con emojis en consolas Windows)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Zona horaria de Peru (UTC-5, sin horario de verano).
try:
    from zoneinfo import ZoneInfo
    _ZONA_PERU = ZoneInfo("America/Lima")
except Exception:
    _ZONA_PERU = timezone(timedelta(hours=-5))

def hora_actual_peru():
    """Fecha y hora actual en la zona horaria de Peru (naive para MySQL)."""
    return datetime.now(_ZONA_PERU).replace(tzinfo=None)

def cargar_entorno():
    """Carga variables desde ../.env sin sobrescribir las del servidor."""
    archivo_env = Path(__file__).resolve().parent.parent / ".env"
    if not archivo_env.is_file():
        return
    for linea in archivo_env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


cargar_entorno()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY debe configurarse en el entorno del servidor")
app.config.update(
    TEMPLATES_AUTO_RELOAD=os.environ.get("DEBUG", "false").lower() == "true",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true",
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
)

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "static/img/productos")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
if not all((DB_USER, DB_PASSWORD, DB_HOST, DB_NAME)):
    raise RuntimeError("Faltan variables de conexión de base de datos")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/{DB_NAME}"
)

# =============================================
# MICROSERVICIOS: UNA BASE DE DATOS POR SERVICIO
# Cada microservicio usa SU propio schema (bind).
# La configuracion sale de ms_config.json (repositorio), con prioridad
# a las variables de entorno y fallback final a la BD principal (DB_NAME)
# para no romper el sistema existente.
# =============================================
_ms_config = {}
_ruta_ms_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ms_config.json")
if os.path.exists(_ruta_ms_config):
    try:
        with open(_ruta_ms_config, "r", encoding="utf-8") as _f:
            _ms_config = json.load(_f)
    except Exception:
        _ms_config = {}

MS_CONFIG = {
    "ventas":     os.environ.get("MS_VENTAS_DB", _ms_config.get("ventas", DB_NAME)),
    "inventario": os.environ.get("MS_INVENTARIO_DB", _ms_config.get("inventario", DB_NAME)),
    "usuarios":   os.environ.get("MS_USUARIOS_DB", _ms_config.get("usuarios", DB_NAME)),
    "clientes":   os.environ.get("MS_CLIENTES_DB", _ms_config.get("clientes", DB_NAME)),
}
app.config["SQLALCHEMY_BINDS"] = {
    servicio: f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/{quote_plus(db_nombre)}"
    for servicio, db_nombre in MS_CONFIG.items()
}

# Comunicacion servicio a servicio (HTTP + token interno)
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", _ms_config.get("service_token", "librospe-interno-dev"))
app.config["SERVICE_TOKEN"] = SERVICE_TOKEN
app.config["MS_INVENTARIO_URL"] = os.environ.get(
    "MS_INVENTARIO_URL", _ms_config.get("inventario_url", "http://127.0.0.1:8001"))
app.config["MS_VENTAS_URL"] = os.environ.get("MS_VENTAS_URL", _ms_config.get("ventas_url", "http://127.0.0.1:8002"))
app.config["MS_USUARIOS_URL"] = os.environ.get("MS_USUARIOS_URL", _ms_config.get("usuarios_url", "http://127.0.0.1:8003"))
app.config["MS_CLIENTES_URL"] = os.environ.get("MS_CLIENTES_URL", _ms_config.get("clientes_url", "http://127.0.0.1:8004"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"ssl": {"ssl_mode": "REQUIRED"}},
    "pool_pre_ping": True,
    "pool_recycle": 280,
}


EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_FROM = os.environ.get("EMAIL_FROM", EMAIL_USER)


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class Bloqueo(db.Model):
    __tablename__ = "bloqueos"
    id = db.Column(db.Integer, primary_key=True)
    tipo_usuario = db.Column(db.Enum('sistema', 'cliente'), nullable=False)
    usuario_sistema_id = db.Column(db.Integer, db.ForeignKey("usuarios_sistema.id"), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    motivo = db.Column(db.String(255), nullable=True)
    bloqueado_por = db.Column(db.Integer, db.ForeignKey("usuarios_sistema.id"), nullable=True)
    fecha_bloqueo = db.Column(db.DateTime, default=datetime.now)
    fecha_desbloqueo = db.Column(db.DateTime, nullable=True)
    desbloqueado_por = db.Column(db.Integer, db.ForeignKey("usuarios_sistema.id"), nullable=True)
    estado = db.Column(db.Boolean, default=True)
    permanente = db.Column(db.Boolean, default=False)
    minutos_bloqueo = db.Column(db.Integer, nullable=True)

class IntentosLogin(db.Model):
    __tablename__ = "intentos_login"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150))
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)  # ← NUEVO
    usuario_sistema_id = db.Column(db.Integer, db.ForeignKey("usuarios_sistema.id"), nullable=True)  # ← NUEVO
    ip = db.Column(db.String(45))
    intentos = db.Column(db.Integer, default=1)
    ultimo_intento = db.Column(db.DateTime, default=datetime.now)
    usuarios_distintos = db.Column(db.Integer, default=0)
    ips_bloqueadas = db.Column(db.DateTime, nullable=True)  
    email_bloqueado = db.Column(db.DateTime, nullable=True)
    intentos_totales = db.Column(db.Integer, default=0)  # ← NUEVO

class Proveedor(db.Model):
    __tablename__ = "proveedores"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    contacto = db.Column(db.String(20), nullable=False)
    ruc_empresa_id = db.Column(db.Integer, db.ForeignKey("ruc_empresas.id"), nullable=True)
    estado = db.Column(db.Integer, default=1)
    productos = db.relationship("Producto", back_populates="proveedor")

class Producto(db.Model):
    __tablename__ = "productos"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    cantidad = db.Column(db.Integer, default=0)
    stock_minimo = db.Column(db.Integer, default=5)
    stock_maximo = db.Column(db.Integer, default=100)
    proveedor_id = db.Column(db.Integer, db.ForeignKey("proveedores.id"), nullable=True)
    precio = db.Column(db.Numeric(10,2), default=0.0)
    costo = db.Column(db.Numeric(10,2), nullable=True)  # precio de compra (solo admin)
    imagen = db.Column(db.String(255))
    destacado = db.Column(db.Integer, default=0)
    precio_oferta = db.Column(db.Numeric(10,2), nullable=True) 
    codigo_barras = db.Column(db.String(50), nullable=True)
    # La columna existe en la tabla productos (BD_Libros.sql) pero faltaba en el
    # modelo: /inventario y /stock-bajo filtran por ella y reventaban con
    # AttributeError. Sin esto ninguna de las dos rutas carga.
    estado = db.Column(db.Integer, default=1)
    id_categoria = db.Column(db.Integer, db.ForeignKey("categorias.id_categoria"), nullable=True)
    
    ventas = db.relationship("Venta", back_populates="producto")
    proveedor = db.relationship("Proveedor", back_populates="productos")
    categoria_rel = db.relationship("Categoria", back_populates="productos")  

class UsuarioSistema(db.Model):
    __tablename__ = "usuarios_sistema"
    id = db.Column(db.Integer, primary_key=True)
    correo = db.Column(db.String(150), unique=True, nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    clave = db.Column(db.String(255), nullable=False)
    estado = db.Column(db.Integer, default=1)
    rol_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    rol = db.Column(db.String(20), nullable=False)  # ← Mantener para compatibilidad
    documento = db.Column(db.String(20), nullable=True)  # DNI o Carnet de Extranjería
    debe_cambiar_clave = db.Column(db.Integer, default=0)  # 1 = debe cambiar la contraseña al entrar
    ventas = db.relationship("Venta", back_populates="vendedor")

class Categoria(db.Model):
    __tablename__ = "categorias"
    id_categoria = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=True)
    
    productos = db.relationship("Producto", back_populates="categoria_rel") 
class Venta(db.Model):
    __tablename__ = "ventas"
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    vendedor_id = db.Column(db.Integer, db.ForeignKey("usuarios_sistema.id"), nullable=False)
    fecha_venta = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cantidad = db.Column(db.Integer, default=1)
    tipo_comprobante = db.Column(db.String(20), default="boleta")
    numero_comprobante = db.Column(db.String(50), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    pedido_id = db.Column(db.Integer, nullable=True)
    estado = db.Column(db.Integer, default=1)
    # Datos de facturación del cliente (boleta/factura)
    cliente_nombres = db.Column(db.String(100), nullable=True)
    cliente_apellidos = db.Column(db.String(100), nullable=True)
    cliente_documento = db.Column(db.String(20), nullable=True)
    cliente_tipo_documento = db.Column(db.String(30), nullable=True)  # RUC | DNI | Carnet de Extranjería
    cliente_email = db.Column(db.String(150), nullable=True)
    cliente_direccion = db.Column(db.Text, nullable=True)
    cliente_direccion_fiscal = db.Column(db.Text, nullable=True)
    cliente_razon_social = db.Column(db.String(200), nullable=True)
    metodo_pago = db.Column(db.String(20), default="efectivo")
    monto_recibido = db.Column(db.Numeric(10,2), nullable=True)
    vuelto = db.Column(db.Numeric(10,2), nullable=True)
    producto = db.relationship("Producto", back_populates="ventas")
    vendedor = db.relationship("UsuarioSistema", back_populates="ventas")
    cliente = db.relationship("Cliente", back_populates="ventas")

    @property
    def proveedor(self):
        return self.producto.proveedor

    @property
    def cliente_nombre_completo(self):
        if self.cliente_nombres and self.cliente_apellidos:
            return f"{self.cliente_nombres} {self.cliente_apellidos}"
        return self.cliente_nombres or ""

class Caja(db.Model):
    __tablename__ = "cajas"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios_sistema.id"), nullable=False)
    monto_inicial = db.Column(db.Numeric(10,2), default=0)
    fecha_apertura = db.Column(db.DateTime, default=datetime.now)
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    monto_esperado = db.Column(db.Numeric(10,2), nullable=True)
    monto_real = db.Column(db.Numeric(10,2), nullable=True)
    diferencia = db.Column(db.Numeric(10,2), nullable=True)
    estado = db.Column(db.String(20), default="abierta")
    usuario = db.relationship("UsuarioSistema")

class Auditoria(db.Model):
    __tablename__ = "auditoria"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios_sistema.id"), nullable=True)
    accion = db.Column(db.String(50), nullable=False)
    modulo = db.Column(db.String(50), nullable=False)
    detalle = db.Column(db.Text, nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.now)

class Permiso(db.Model):
    __tablename__ = "permisos"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False, unique=True)
    descripcion = db.Column(db.String(200), nullable=True)

class RolPermiso(db.Model):
    __tablename__ = "rol_permisos"
    id = db.Column(db.Integer, primary_key=True)
    rol_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    permiso_id = db.Column(db.Integer, db.ForeignKey("permisos.id"), nullable=False)

class Cliente(db.Model):
    __tablename__ = "clientes"
    id = db.Column(db.Integer, primary_key=True)
    dni = db.Column(db.String(8))
    ruc = db.Column(db.String(11), nullable=True)
    ce = db.Column(db.String(9), nullable=True)  # ← Carnet de Extranjería (persona natural)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(150), unique=True, nullable=False)  # ← CAMBIADO de email a correo
    telefono = db.Column(db.String(15))
    direccion = db.Column(db.Text)
    departamento = db.Column(db.String(100), nullable=True)
    provincia = db.Column(db.String(100), nullable=True)
    distrito = db.Column(db.String(150), nullable=True)
    clave = db.Column(db.String(255), nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.now)
    puntos = db.Column(db.Integer, default=0)
    token_recuperacion = db.Column(db.String(100), nullable=True)
    token_expiracion = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.Integer, default=1)  # ← AGREGAR campo estado
    pedidos = db.relationship("Pedido", back_populates="cliente")
    ventas = db.relationship("Venta", back_populates="cliente")
class Rol(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    estado = db.Column(db.Integer, default=1)

class Departamento(db.Model):
    __tablename__ = "departamentos"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    ubigeo = db.Column(db.String(2), nullable=True)
    provincias = db.relationship("Provincia", back_populates="departamento")

class Provincia(db.Model):
    __tablename__ = "provincias"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    ubigeo = db.Column(db.String(4), nullable=True)
    departamento_id = db.Column(db.Integer, db.ForeignKey("departamentos.id"), nullable=True)
    departamento = db.relationship("Departamento", back_populates="provincias")
    distritos = db.relationship("Distrito", back_populates="provincia")

class Distrito(db.Model):
    __tablename__ = "distritos"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    ubigeo = db.Column(db.String(6), nullable=True)
    provincia_id = db.Column(db.Integer, db.ForeignKey("provincias.id"), nullable=True)
    departamento_id = db.Column(db.Integer, db.ForeignKey("departamentos.id"), nullable=True)
    provincia = db.relationship("Provincia", back_populates="distritos")

class Pedido(db.Model):
    __tablename__ = "pedidos"
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"))
    fecha_pedido = db.Column(db.DateTime, default=datetime.now)
    estado = db.Column(db.String(20), default="pendiente")
    total = db.Column(db.Float)
    direccion_entrega = db.Column(db.Text)
    tipo_entrega = db.Column(db.String(20), default="recojo")
    # Punto de entrega en el mapa (migracion_delivery_mapa.sql).
    # NULL cuando el geocodificado falla: el admin lo coloca a mano.
    lat = db.Column(db.Numeric(10, 7), nullable=True)
    lng = db.Column(db.Numeric(10, 7), nullable=True)
    geo_precision = db.Column(db.String(10), nullable=True)  # exacta|aproximada|manual
    nota = db.Column(db.Text)
    # Confirmación de entrega (delivery)
    nombre_recibe = db.Column(db.String(200), nullable=True)
    dni_recibe = db.Column(db.String(20), nullable=True)
    fecha_entrega = db.Column(db.DateTime, nullable=True)
    confirmado_por = db.Column(db.String(100), nullable=True)
    cliente_confirmo = db.Column(db.Integer, default=0)
    fecha_confirmacion_cliente = db.Column(db.DateTime, nullable=True)
    cliente = db.relationship("Cliente", back_populates="pedidos")
    detalles = db.relationship("DetallePedido", back_populates="pedido")

class DetallePedido(db.Model):
    __tablename__ = "detalle_pedido"
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"))
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"))
    cantidad = db.Column(db.Integer)
    precio_unitario = db.Column(db.Float)
    subtotal = db.Column(db.Float)
    pedido = db.relationship("Pedido", back_populates="detalles")
    producto = db.relationship("Producto")

class RucEmpresa(db.Model):
    __tablename__ = "ruc_empresas"
    id = db.Column(db.Integer, primary_key=True)
    ruc = db.Column(db.String(11), unique=True, nullable=False)
    razon_social = db.Column(db.String(200), nullable=False)
    direccion = db.Column(db.Text, nullable=True)


def _obtener_cliente_por_correo(email):
    """Producción real: busca cliente en microservicio dueño (librospe_ms_clientes) via bind.
    Fallback a librospe_db para compatibilidad con clientes antiguos antes de la migración."""
    # Intenta microservicio primero
    try:
        try:
            engine = db.get_engine(bind="clientes")
        except Exception:
            engine = db.engines.get("clientes") if hasattr(db, "engines") else None
        if engine is not None:
            row = db.session.execute(
                text("SELECT id, correo, clave, nombres, apellidos, estado, telefono, direccion, dni, ce, ruc, departamento, provincia, distrito FROM clientes WHERE correo=:c"),
                {"c": email}, bind_arguments={"bind": engine}
            ).mappings().first()
            if row:
                # Objeto simple con mismos atributos que ORM Cliente para login
                class _Cli: pass
                c = _Cli()
                c.id = row["id"]; c.correo = row["correo"]; c.clave = row["clave"]
                c.nombres = row["nombres"]; c.apellidos = row["apellidos"]; c.estado = row["estado"]
                c.telefono = row["telefono"]; c.direccion = row["direccion"]; c.dni = row["dni"]
                c.ce = row["ce"]; c.ruc = row["ruc"]; c.departamento = row["departamento"]
                c.provincia = row["provincia"]; c.distrito = row["distrito"]
                c._is_ms = True
                return c
    except Exception:
        pass
    obj = Cliente.query.filter_by(correo=email).first()
    if obj is not None:
        try: obj._is_ms = False
        except Exception: pass
    return obj

def _obtener_cliente_por_id(cid):
    """Busca cliente por ID en microservicio primero, fallback librospe_db."""
    try:
        try:
            engine = db.get_engine(bind="clientes")
        except Exception:
            engine = db.engines.get("clientes") if hasattr(db, "engines") else None
        if engine is not None:
            row = db.session.execute(
                text("SELECT id, correo, clave, nombres, apellidos, estado, telefono, direccion, dni, ce, ruc, departamento, provincia, distrito FROM clientes WHERE id=:id"),
                {"id": cid}, bind_arguments={"bind": engine}
            ).mappings().first()
            if row:
                class _Cli: pass
                c = _Cli()
                c.id = row["id"]; c.correo = row["correo"]; c.clave = row["clave"]
                c.nombres = row["nombres"]; c.apellidos = row["apellidos"]; c.estado = row["estado"]
                c.telefono = row["telefono"]; c.direccion = row["direccion"]; c.dni = row["dni"]
                c.ce = row["ce"]; c.ruc = row["ruc"]; c.departamento = row["departamento"]
                c.provincia = row["provincia"]; c.distrito = row["distrito"]
                c._is_ms = True
                return c
    except Exception:
        pass
    obj = Cliente.query.get(cid)
    if obj is not None:
        try: obj._is_ms = False
        except Exception: pass
    return obj
def _asegurar_cliente_en_principal(cid):
    """Los clientes nuevos se crean solo en el microservicio dueño
    (librospe_ms_clientes); la principal necesita la fila por la FK
    pedidos.cliente_id -> clientes.id. Inserta la fila si falta."""
    if cid is None:
        return
    try:
        if Cliente.query.get(cid) is not None:
            return
        try:
            engine = db.get_engine(bind="clientes")
        except Exception:
            engine = db.engines.get("clientes") if hasattr(db, "engines") else None
        if engine is None:
            return
        row = db.session.execute(
            text("""SELECT id, dni, ruc, ce, nombres, apellidos, correo, telefono, 
direccion,
                            departamento, provincia, distrito, clave, puntos, estado, fecha_registro
                     FROM clientes WHERE id=:id"""),
            {"id": cid}, bind_arguments={"bind": engine}
        ).mappings().first()
        if row is None:
            return
        _insertar_cliente_principal(row)
    except Exception:
        db.session.rollback()


def _insertar_cliente_principal(row):
    """Inserta en librospe_db la fila leída del microservicio.
    Si ya existe otra fila con el mismo correo y distinto id (dato desalineado),
    se reemplaza únicamente cuando esa fila no tiene ventas/pedidos; si los tiene,
    no se toca y el pedido fallará con un error claro en su lugar."""
    def insertar():
        db.session.add(Cliente(
            id=row["id"], dni=row["dni"], ruc=row["ruc"], ce=row["ce"],
            nombres=row["nombres"], apellidos=row["apellidos"], correo=row["correo"],
            telefono=row["telefono"], direccion=row["direccion"],
            departamento=row["departamento"], provincia=row["provincia"],
            distrito=row["distrito"], clave=row["clave"],
            puntos=row["puntos"] or 0,
            estado=row["estado"] if row["estado"] is not None else 1,
            fecha_registro=row["fecha_registro"],
        ))
        db.session.commit()

    try:
        insertar()
        return True
    except IntegrityError:
        db.session.rollback()
    except Exception:
        db.session.rollback()
        return False

    # Correo ya registrado en la principal con otro id
    dup = db.session.execute(
        text("SELECT id FROM clientes WHERE correo=:c AND id!=:id"),
        {"c": row["correo"], "id": row["id"]}
    ).scalar()
    if dup is None:
        return False
    n_doc = db.session.execute(
        text("""SELECT (SELECT COUNT(*) FROM pedidos WHERE cliente_id=:i)
                   + (SELECT COUNT(*) FROM ventas WHERE cliente_id=:i)
                   + (SELECT COUNT(*) FROM intentos_login WHERE cliente_id=:i)"""),
        {"i": dup}
    ).scalar() or 0
    if n_doc:
        print(f"⚠️ Cliente {row['id']}: el correo {row['correo']} ya existe en "
              f"librospe_db con id {dup} y {n_doc} documento(s); no se reemplaza.")
        return False
    try:
        db.session.execute(text("DELETE FROM clientes WHERE id=:i"), {"i": dup})
        db.session.commit()
        insertar()
        print(f"🔄 Cliente {row['id']}: fila desalineada (id {dup}) reemplazada en librospe_db")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ No se pudo reemplazar la fila desalineada (id {dup}): {e}")
        return False

def _guardar_datos_cliente(cid, campos):
    """Persiste cambios de perfil del cliente en su DUEÑO de datos:
    microservicio clientes (bind) si es MS, o librospe_db si es legacy."""
    if cid is None or not campos:
        return
    try:
        cli = _obtener_cliente_por_id(cid)
        if cli is None:
            return
        if getattr(cli, "_is_ms", False):
            sets = ", ".join(f"{c}=:{c}" for c in campos)
            engine = db.get_engine(bind="clientes") if hasattr(db, "get_engine") else None
            db.session.execute(
                text(f"UPDATE clientes SET {sets} WHERE id=:id"),
                {**campos, "id": cid}, bind_arguments={"bind": engine}
            )
        else:
            orm = Cliente.query.get(cid)
            if orm is None:
                return
            for c, v in campos.items():
                setattr(orm, c, v)
        db.session.commit()
    except Exception:
        db.session.rollback()

def obtener_ip_cliente():
    """Obtiene la IP real del cliente"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

def registrar_intento_fallido(email, ip, es_cliente=False):
    """
    Registra un intento fallido de login con bloqueo progresivo:
    - 3 intentos fallidos → bloqueo temporal (10 minutos)
    - 5 intentos fallidos → bloqueo permanente (solo admin desbloquea)
    """
    ahora = datetime.now()
    
    # Verificar si el email existe (clientes: busca en microservicio dueño primero)
    email_existe = False
    if es_cliente:
        email_existe = _obtener_cliente_por_correo(email) is not None
    else:
        email_existe = UsuarioSistema.query.filter_by(correo=email).first() is not None
    
    # Verificar bloqueo de IP
    ip_bloqueada = IntentosLogin.query.filter(
        IntentosLogin.ip == ip,
        IntentosLogin.ips_bloqueadas > ahora
    ).first()
    
    if ip_bloqueada:
        return {"bloqueado": True, "tipo": "ip", "mensaje": "IP bloqueada por 10 minutos"}
    
    # Si el email no existe, registrar intento con email inexistente
    if not email_existe:
        registro = IntentosLogin.query.filter_by(email=email).first()
        
        if not registro:
            registro = IntentosLogin(
                email=email, 
                ip=ip, 
                intentos=1, 
                ultimo_intento=ahora, 
                usuarios_distintos=0,
                intentos_totales=1
            )
            db.session.add(registro)
            db.session.commit()
            return {"bloqueado": False, "intentos_restantes": 999, "email_no_existe": True}
        
        registro.intentos += 1
        registro.intentos_totales += 1
        registro.ultimo_intento = ahora
        registro.ip = ip
        db.session.commit()
        
        emails_fallidos = IntentosLogin.query.filter(
            IntentosLogin.ip == ip,
            IntentosLogin.intentos >= 1
        ).count()
        
        if emails_fallidos >= 2 and not registro.ips_bloqueadas:
            IntentosLogin.query.filter(
                IntentosLogin.ip == ip
            ).update({IntentosLogin.ips_bloqueadas: ahora + timedelta(minutes=10)})
            db.session.commit()
            return {"bloqueado": True, "tipo": "ip", "mensaje": "IP bloqueada por 10 minutos (múltiples intentos con emails inexistentes)"}
        
        return {"bloqueado": False, "intentos_restantes": 999, "email_no_existe": True}
    
    # ==========================================
    # EL EMAIL EXISTE - PROCESAR INTENTOS
    # ==========================================
    registro = IntentosLogin.query.filter_by(email=email).first()
    
    if not registro:
        registro = IntentosLogin(
            email=email, 
            ip=ip, 
            intentos=1, 
            ultimo_intento=ahora, 
            usuarios_distintos=1,  # ← NUEVO: Primer usuario desde esta IP
            intentos_totales=1
        )
        db.session.add(registro)
        db.session.commit()
        return {"bloqueado": False, "intentos_restantes": 2, "intentos_totales": 1}
    
    # ==========================================
    # ACTUALIZAR usuarios_distintos
    # ==========================================
    # Contar cuántos emails diferentes han intentado login desde esta IP
    emails_desde_ip = db.session.execute(text("""
        SELECT COUNT(DISTINCT email) 
        FROM intentos_login 
        WHERE ip = :ip 
        AND email != :email
    """), {"ip": ip, "email": email}).scalar()
    
    # Si es un nuevo email desde esta IP, incrementar usuarios_distintos
    if emails_desde_ip > 0:
        # Verificar si este email ya existe en intentos_login para esta IP
        existe_email_ip = db.session.execute(text("""
            SELECT COUNT(*) 
            FROM intentos_login 
            WHERE ip = :ip 
            AND email = :email
        """), {"ip": ip, "email": email}).scalar()
        
        if existe_email_ip == 0:
            # Es un nuevo email desde esta IP
            registro.usuarios_distintos = emails_desde_ip + 1
        else:
            # El email ya existe, mantener el contador
            registro.usuarios_distintos = emails_desde_ip
    else:
        # Es el primer email desde esta IP
        registro.usuarios_distintos = 1
    
    # Incrementar contadores
    registro.intentos += 1
    registro.intentos_totales += 1
    registro.ultimo_intento = ahora
    registro.ip = ip
    
    # ==========================================
    # VERIFICAR BLOQUEO POR IP (múltiples usuarios distintos)
    # ==========================================
    # Si hay 2 o más usuarios distintos desde esta IP, bloquear la IP
    if registro.usuarios_distintos >= 2 and not registro.ips_bloqueadas:
        registro.ips_bloqueadas = ahora + timedelta(minutes=10)
        db.session.commit()
        return {"bloqueado": True, "tipo": "ip", "mensaje": "IP bloqueada por 10 minutos (múltiples usuarios desde la misma IP)"}
    
    # ==========================================
    # VERIFICAR BLOQUEO PERMANENTE
    # ==========================================
    # Verificar si ya está bloqueado permanentemente
    if es_cliente:
        bloqueo_permanente = db.session.execute(text("""
            SELECT id FROM bloqueos 
            WHERE cliente_id = (SELECT id FROM clientes WHERE correo = :email)
            AND tipo_usuario = 'cliente' 
            AND estado = 1 
            AND permanente = 1
        """), {"email": email}).fetchone()
    else:
        bloqueo_permanente = db.session.execute(text("""
            SELECT id FROM bloqueos 
            WHERE usuario_sistema_id = (SELECT id FROM usuarios_sistema WHERE correo = :email)
            AND tipo_usuario = 'sistema' 
            AND estado = 1 
            AND permanente = 1
        """), {"email": email}).fetchone()
    
    if bloqueo_permanente:
        db.session.commit()
        return {"bloqueado": True, "tipo": "permanente", "mensaje": "CUENTA BLOQUEADA PERMANENTEMENTE. Contacta al administrador."}
    
    # ==========================================
    # NIVEL 1: 3 INTENTOS → BLOQUEO TEMPORAL (10 min)
    # ==========================================
    if registro.intentos >= 3 and not registro.email_bloqueado:
        registro.email_bloqueado = ahora + timedelta(minutes=10)
        
        if es_cliente:
            cliente = Cliente.query.filter_by(correo=email).first()
            if cliente:
                existe_bloqueo = db.session.execute(text("""
                    SELECT id FROM bloqueos 
                    WHERE cliente_id = :cliente_id 
                    AND tipo_usuario = 'cliente' 
                    AND estado = 1
                    AND permanente = 0
                """), {"cliente_id": cliente.id}).fetchone()
                
                if not existe_bloqueo:
                    db.session.execute(text("""
                        INSERT INTO bloqueos 
                        (tipo_usuario, cliente_id, motivo, fecha_bloqueo, bloqueado_por, estado, permanente, minutos_bloqueo)
                        VALUES ('cliente', :cliente_id, :motivo, NOW(), 1, 1, 0, 10)
                    """), {
                        "cliente_id": cliente.id,
                        "motivo": "Bloqueo temporal por 3 intentos fallidos de login"
                    })
        else:
            usuario = UsuarioSistema.query.filter_by(correo=email).first()
            if usuario:
                existe_bloqueo = db.session.execute(text("""
                    SELECT id FROM bloqueos 
                    WHERE usuario_sistema_id = :usuario_id 
                    AND tipo_usuario = 'sistema' 
                    AND estado = 1
                    AND permanente = 0
                """), {"usuario_id": usuario.id}).fetchone()
                
                if not existe_bloqueo:
                    db.session.execute(text("""
                        INSERT INTO bloqueos 
                        (tipo_usuario, usuario_sistema_id, motivo, fecha_bloqueo, bloqueado_por, estado, permanente, minutos_bloqueo)
                        VALUES ('sistema', :usuario_id, :motivo, NOW(), 1, 1, 0, 10)
                    """), {
                        "usuario_id": usuario.id,
                        "motivo": "Bloqueo temporal por 3 intentos fallidos de login"
                    })
        
        db.session.commit()
        return {"bloqueado": True, "tipo": "email", "mensaje": "Correo bloqueado temporalmente por 10 minutos. 3 intentos fallidos."}
    
    # ==========================================
    # NIVEL 2: 5 INTENTOS → BLOQUEO PERMANENTE
    # ==========================================
    if registro.intentos_totales >= 5:
        registro.email_bloqueado = None
        registro.intentos = 0
        db.session.commit()
        
        if es_cliente:
            cliente = Cliente.query.filter_by(correo=email).first()
            if cliente:
                existe_permanente = db.session.execute(text("""
                    SELECT id FROM bloqueos 
                    WHERE cliente_id = :cliente_id 
                    AND tipo_usuario = 'cliente' 
                    AND estado = 1
                    AND permanente = 1
                """), {"cliente_id": cliente.id}).fetchone()
                
                if not existe_permanente:
                    db.session.execute(text("""
                        INSERT INTO bloqueos 
                        (tipo_usuario, cliente_id, motivo, fecha_bloqueo, bloqueado_por, estado, permanente)
                        VALUES ('cliente', :cliente_id, :motivo, NOW(), 1, 1, 1)
                    """), {
                        "cliente_id": cliente.id,
                        "motivo": "BLOQUEO PERMANENTE por 5 intentos fallidos de login"
                    })
        else:
            usuario = UsuarioSistema.query.filter_by(correo=email).first()
            if usuario:
                existe_permanente = db.session.execute(text("""
                    SELECT id FROM bloqueos 
                    WHERE usuario_sistema_id = :usuario_id 
                    AND tipo_usuario = 'sistema' 
                    AND estado = 1
                    AND permanente = 1
                """), {"usuario_id": usuario.id}).fetchone()
                
                if not existe_permanente:
                    db.session.execute(text("""
                        INSERT INTO bloqueos 
                        (tipo_usuario, usuario_sistema_id, motivo, fecha_bloqueo, bloqueado_por, estado, permanente)
                        VALUES ('sistema', :usuario_id, :motivo, NOW(), 1, 1, 1)
                    """), {
                        "usuario_id": usuario.id,
                        "motivo": "BLOQUEO PERMANENTE por 5 intentos fallidos de login"
                    })
        
        db.session.commit()
        return {"bloqueado": True, "tipo": "permanente", "mensaje": "CUENTA BLOQUEADA PERMANENTEMENTE por 5 intentos fallidos. Contacta al administrador."}
    
    # ==========================================
    # MENOS DE 3 INTENTOS → AÚN NO BLOQUEADO
    # ==========================================
    db.session.commit()
    
    intentos_restantes_temporales = 3 - registro.intentos
    intentos_restantes_permanentes = 5 - registro.intentos_totales
    
    return {
        "bloqueado": False, 
        "intentos_restantes": intentos_restantes_temporales if intentos_restantes_temporales > 0 else 0,
        "intentos_totales": registro.intentos_totales,
        "intentos_para_bloqueo_permanente": intentos_restantes_permanentes if intentos_restantes_permanentes > 0 else 0,
        "usuarios_distintos": registro.usuarios_distintos,
        "mensaje": f"Intento {registro.intentos_totales} de 5. {intentos_restantes_temporales} intentos para bloqueo temporal, {intentos_restantes_permanentes} para bloqueo permanente."
    }

def verificar_bloqueo_ip(ip):
    """Verifica si la IP está bloqueada"""
    ahora = datetime.now()
    bloqueado = IntentosLogin.query.filter(
        IntentosLogin.ip == ip,
        IntentosLogin.ips_bloqueadas > ahora
    ).first()
    
    if bloqueado:
        print(f"IP {ip} BLOQUEADA hasta {bloqueado.ips_bloqueadas}", flush=True)
        return True
    
    print(f"IP {ip} NO BLOQUEADA", flush=True)
    return False


def verificar_bloqueo_email(email):
    """
    Verifica si el email está bloqueado (temporal o permanentemente)
    Retorna True si está bloqueado, False si no
    """
    ahora = datetime.now()
    
    # 1. Verificar bloqueo temporal en intentos_login
    registro = IntentosLogin.query.filter_by(email=email).first()
    if registro and registro.email_bloqueado and registro.email_bloqueado > ahora:
        print(f"Email {email} BLOQUEADO TEMPORALMENTE hasta {registro.email_bloqueado}", flush=True)
        return True
    
    # 2. Verificar bloqueo permanente en tabla bloqueos
    # Primero verificar si es un cliente
    cliente = Cliente.query.filter_by(correo=email).first()
    if cliente:
        bloqueo = db.session.execute(text("""
            SELECT id FROM bloqueos 
            WHERE cliente_id = :cliente_id 
            AND tipo_usuario = 'cliente' 
            AND estado = 1 
            AND permanente = 1
        """), {"cliente_id": cliente.id}).fetchone()
        
        if bloqueo:
            print(f"Email {email} BLOQUEADO PERMANENTEMENTE (cliente)", flush=True)
            return True
    
    # Verificar si es un usuario del sistema
    usuario = UsuarioSistema.query.filter_by(correo=email).first()
    if usuario:
        bloqueo = db.session.execute(text("""
            SELECT id FROM bloqueos 
            WHERE usuario_sistema_id = :usuario_id 
            AND tipo_usuario = 'sistema' 
            AND estado = 1 
            AND permanente = 1
        """), {"usuario_id": usuario.id}).fetchone()
        
        if bloqueo:
            print(f"Email {email} BLOQUEADO PERMANENTEMENTE (usuario sistema)", flush=True)
            return True
    
    return False


def limpiar_intentos_exitosos(email, ip):
    """
    Limpia los intentos fallidos cuando el login es exitoso.
    - Resetea intentos a 0
    - Resetea intentos_totales a 0 (para que empiece de nuevo el contador)
    - Elimina bloqueos temporales
    """
    try:
        print(f"🔍 Limpiando intentos para {email}")
        
        # 1. Buscar el registro de intentos
        registro = IntentosLogin.query.filter_by(email=email).first()
        
        if registro:
            # Resetear TODO
            registro.intentos = 0
            registro.intentos_totales = 0  # ← NUEVO: Resetear también
            registro.email_bloqueado = None
            registro.ultimo_intento = datetime.now()
            db.session.commit()
            print(f"✅ Intentos y totales reseteados para {email}")
        else:
            print(f"ℹ️ No hay registro de intentos para {email}")
        
        # 2. Desactivar bloqueos temporales en tabla 'bloqueos'
        # Buscar si es cliente
        cliente = Cliente.query.filter_by(correo=email).first()
        if cliente:
            db.session.execute(text("""
                UPDATE bloqueos 
                SET estado = 0, fecha_desbloqueo = NOW() 
                WHERE cliente_id = :cliente_id 
                AND tipo_usuario = 'cliente' 
                AND permanente = 0 
                AND estado = 1
            """), {"cliente_id": cliente.id})
            db.session.commit()
            print(f"✅ Bloqueos temporales desactivados para cliente {email}")
        
        # Buscar si es usuario del sistema
        usuario = UsuarioSistema.query.filter_by(correo=email).first()
        if usuario:
            db.session.execute(text("""
                UPDATE bloqueos 
                SET estado = 0, fecha_desbloqueo = NOW() 
                WHERE usuario_sistema_id = :usuario_id 
                AND tipo_usuario = 'sistema' 
                AND permanente = 0 
                AND estado = 1
            """), {"usuario_id": usuario.id})
            db.session.commit()
            print(f"✅ Bloqueos temporales desactivados para usuario {email}")
        
        # 3. Verificar si la IP ya no tiene bloqueos activos
        ahora = datetime.now()
        emails_bloqueados = IntentosLogin.query.filter(
            IntentosLogin.ip == ip,
            IntentosLogin.email_bloqueado > ahora
        ).count()
        
        if emails_bloqueados == 0:
            IntentosLogin.query.filter_by(ip=ip).update({IntentosLogin.ips_bloqueadas: None})
            db.session.commit()
            print(f"✅ IP {ip} desbloqueada")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error al limpiar intentos: {e}")
        return False

def limpiar_bloqueos_expirados():
    """Limpia bloqueos temporales que ya expiraron (no toca los permanentes)"""
    ahora = datetime.now()
    
    # Limpiar bloqueos temporales en intentos_login
    IntentosLogin.query.filter(
        IntentosLogin.email_bloqueado < ahora,
        IntentosLogin.email_bloqueado.isnot(None)
    ).update({IntentosLogin.email_bloqueado: None, IntentosLogin.intentos: 0})
    
    IntentosLogin.query.filter(
        IntentosLogin.ips_bloqueadas < ahora,
        IntentosLogin.ips_bloqueadas.isnot(None)
    ).update({IntentosLogin.ips_bloqueadas: None})
    
    # Limpiar bloqueos temporales en tabla bloqueos (NO los permanentes)
    db.session.execute(text("""
        UPDATE bloqueos 
        SET estado = 0, fecha_desbloqueo = NOW() 
        WHERE permanente = 0 
        AND estado = 1 
        AND fecha_bloqueo < DATE_SUB(NOW(), INTERVAL minutos_bloqueo MINUTE)
    """))
    
    db.session.commit()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("rol") != "administrador":
            return "Acceso denegado", 403
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# PERMISOS POR ROL CONFIGURABLES
# ============================================
PERMISOS_DISPONIBLES = {
    "gestionar_productos": "Crear, editar y eliminar productos",
    "gestionar_proveedores": "Crear, editar y eliminar proveedores",
    "gestionar_usuarios": "Gestionar usuarios del sistema",
    "ver_dashboard": "Ver el dashboard",
    "ver_caja": "Abrir y cerrar caja",
    "ver_auditoria": "Ver registro de auditoría",
    "ver_reportes": "Ver reportes y exportar",
    "gestionar_bloqueos": "Gestionar bloqueos de seguridad",
}

def tiene_permiso(rol, permiso):
    """Verifica si un rol tiene asignado un permiso."""
    if rol == "administrador":
        return True
    rol_obj = Rol.query.filter_by(nombre=rol).first()
    if not rol_obj:
        return False
    return db.session.query(RolPermiso.id).join(Permiso, RolPermiso.permiso_id == Permiso.id)\
        .filter(RolPermiso.rol_id == rol_obj.id, Permiso.nombre == permiso).first() is not None

def permiso_requerido(nombre_permiso):
    """Decorador: exige que el rol tenga el permiso (el admin siempre lo tiene)."""
    def decorador(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("rol") != "administrador" and not tiene_permiso(session.get("rol"), nombre_permiso):
                flash("❌ No tienes permiso para esta acción", "danger")
                return redirect(url_for("productos"))
            return f(*args, **kwargs)
        return decorated_function
    return decorador

def seed_permisos():
    """Crea los permisos y asigna todos al rol administrador."""
    admin = Rol.query.filter_by(nombre="admin").first() or Rol.query.filter_by(nombre="administrador").first()
    for nombre, desc in PERMISOS_DISPONIBLES.items():
        p = Permiso.query.filter_by(nombre=nombre).first()
        if not p:
            p = Permiso(nombre=nombre, descripcion=desc)
            db.session.add(p)
            db.session.flush()
        if admin:
            existe = RolPermiso.query.filter_by(rol_id=admin.id, permiso_id=p.id).first()
            if not existe:
                db.session.add(RolPermiso(rol_id=admin.id, permiso_id=p.id))
    db.session.commit()

def requerir_permisos_escritura(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("rol") == "vendedor":
            return "Acceso denegado: Los vendedores solo pueden registrar ventas.", 403
        return f(*args, **kwargs)
    return decorated_function

def obtener_token_csrf():
    """Token por sesión para operaciones que modifican datos."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]

# Etiqueta legible de cada tipo de comprobante. Centralizada para que todas
# las vistas muestren lo mismo: antes cada plantilla hacia su if/else y una
# venta tipo 'nota' salia como "BOLETA DE VENTA" en el detalle del cliente.
ETIQUETAS_COMPROBANTE = {
    "boleta": "📄 BOLETA DE VENTA",
    "factura": "🏢 FACTURA ELECTRÓNICA",
    "nota": "📝 NOTA DE VENTA",
    "ninguno": "🚫 SIN COMPROBANTE",
}


def _etiqueta_comprobante(tipo):
    return ETIQUETAS_COMPROBANTE.get(tipo, str(tipo or "").upper() or "NO ESPECIFICADO")


@app.context_processor
def inject_security_context():
    return {"csrf_token": obtener_token_csrf(),
            "ventas_etiqueta_comprobante": ETIQUETAS_COMPROBANTE}

def csrf_protect(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # El CSRF solo importa en metodos que cambian estado. Antes se
        # aplicaba sin mirar el metodo y abortaba tambien los GET, lo que
        # rompia /perfil (que es GET+POST en la misma ruta): un GET normal
        # del navegador no manda token y salia 400.
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return f(*args, **kwargs)
        enviado = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        esperado = session.get("csrf_token", "")
        if not enviado or not esperado or not hmac.compare_digest(enviado, esperado):
            abort(400, "Solicitud no válida o expirada.")
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def agregar_cabeceras_seguridad(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

def login_required_cliente(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "cliente_id" not in session:
            flash("Debes iniciar sesión para continuar", "warning")
            return redirect(url_for("login_cliente"))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_fecha_actual():
    """Inyecta hora_actual_peru() y ahora_peru en todas las plantillas."""
    ahora = hora_actual_peru()
    return {"hora_peru": hora_actual_peru, "ahora_peru": ahora}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generar_token_recuperacion():
    return secrets.token_urlsafe(32)

def registrar_auditoria(accion, modulo, detalle=""):
    """Registra una acción en la tabla de auditoría."""
    try:
        db.session.add(Auditoria(
            usuario_id=session.get("usuario_id"),
            accion=accion,
            modulo=modulo,
            detalle=detalle,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

def rango_periodo(periodo):
    """Devuelve (fecha_inicio, fecha_fin) según el período seleccionado."""
    hoy = datetime.now().date()
    if periodo == "hoy":
        return hoy, hoy
    if periodo == "semana":
        return hoy - timedelta(days=hoy.weekday()), hoy
    if periodo == "mes":
        return hoy.replace(day=1), hoy
    if periodo == "anio":
        return hoy.replace(month=1, day=1), hoy
    return None, None

def verificar_stock_bajo_y_notificar():
    """Envía un correo al administrador si hay productos con stock bajo/agotado."""
    try:
        bajos = Producto.query.filter(Producto.cantidad <= Producto.stock_minimo).all()
        if not bajos:
            return
        admins = UsuarioSistema.query.filter_by(rol="administrador").all()
        destinatarios = [a.correo for a in admins if a.correo]
        if not destinatarios:
            return
        lineas = "".join(
            f"<li><b>{p.nombre}</b>: {p.cantidad} unidades (mínimo {p.stock_minimo or 5})</li>"
            for p in bajos
        )
        asunto = "⚠️ Alerta de stock bajo - Librería Salesiana"
        html = f"<h3>Productos con stock bajo o agotado</h3><ul>{lineas}</ul>"
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM or EMAIL_USER
        msg['To'] = ", ".join(destinatarios)
        msg['Subject'] = asunto
        msg.attach(MIMEText(html, 'html'))
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"❌ Error notificando stock bajo: {e}")

def generar_comprobante_html(venta, producto, precio, cantidad, total, vendedor_nombre=""):
    titulo = "LIBRERÍA SALESIANA DON BOSCO"
    gracias = "¡Gracias por su compra! Que Dios lo bendiga."
    if venta.tipo_comprobante == "factura":
        subtitulo = "FACTURA ELECTRÓNICA"
        documento_label = "RUC"
        documento_valor = venta.cliente_documento or "—"
        direccion_html = f"<p><strong>📍 Dirección:</strong> {venta.cliente_direccion or '—'}</p>"
    elif venta.tipo_comprobante == "nota":
        subtitulo = "NOTA DE VENTA"
        documento_label = "Documento"
        documento_valor = venta.cliente_documento or "—"
        direccion_html = ""
    else:
        subtitulo = "BOLETA DE VENTA ELECTRÓNICA"
        documento_label = "Documento"
        documento_valor = venta.cliente_documento or "—"
        direccion_html = ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Comprobante</title></head>
<body><div style="font-family:Arial;max-width:600px;margin:auto;">
<div style="background:#007bff;color:white;padding:20px;text-align:center;">
<h2>📚 {titulo}</h2><p>{subtitulo}</p><p><strong>N° {venta.numero_comprobante}</strong></p>
</div><div style="padding:20px;">
<p><strong>�� Fecha:</strong> {venta.fecha_venta.strftime('%d/%m/%Y %H:%M')}</p>
<p><strong>👤 Cliente:</strong> {venta.cliente_nombre_completo}</p>
<p><strong>{documento_label}:</strong> {documento_valor}</p>
{direccion_html}
<hr><p><strong>🛒 Producto:</strong> {producto.nombre}</p>
<p><strong>Cantidad:</strong> {cantidad}</p>
<p><strong>Precio:</strong> S/. {precio:.2f}</p>
<p><strong>Total:</strong> S/. {total:.2f}</p>
</div><div style="background:#f8f9fa;text-align:center;padding:10px;">
<p>✨ {gracias} ✨</p>
<p>Válido como comprobante de pago</p>
</div></div></body></html>"""

def numero_a_letras(numero):
    """Convierte un número (hasta millones) a letras en español."""
    unidades = ("cero","uno","dos","tres","cuatro","cinco","seis","siete","ocho","nueve","diez",
                "once","doce","trece","catorce","quince","dieciséis","diecisiete","dieciocho","diecinueve","veinte",
                "veintiuno","veintidós","veintitrés","veinticuatro","veinticinco","veintiséis","veintisiete","veintiocho","veintinueve")
    decenas = ("", "", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa")
    centenas = ("", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos")

    def tres(n):
        if n == 0:
            return ""
        if n == 100:
            return "cien"
        partes = []
        if n >= 100:
            partes.append(centenas[n // 100])
            n %= 100
        if n >= 30:
            partes.append(decenas[n // 10])
            n %= 10
            if n:
                partes.append("y")
        if n:
            partes.append(unidades[n])
        return " ".join(partes).strip()

    if numero == 0:
        return "cero"

    partes = []
    if numero >= 1000000:
        millones, numero = divmod(numero, 1000000)
        partes.append("un millón" if millones == 1 else numero_a_letras(millones) + " millones")
    if numero >= 1000:
        miles, numero = divmod(numero, 1000)
        partes.append("mil" if miles == 1 else numero_a_letras(miles) + " mil")
    if numero:
        partes.append(tres(numero))
    return " ".join(partes)

def enlace_whatsapp(telefono, texto):
    """Enlace wa.me/<numero> con el mensaje precargado.
    Normaliza celulares peruanos: 9XXXXXXXX / 09XXXXXXXX -> 519XXXXXXXX.
    Devuelve None si no hay teléfono utilizable."""
    if not telefono:
        return None
    solo = "".join(ch for ch in str(telefono) if ch.isdigit())
    if not solo:
        return None
    if solo.startswith("51") and len(solo) >= 11:
        numero = solo
    elif solo.startswith("0") and len(solo) >= 9:
        numero = "51" + solo[1:]
    elif len(solo) == 9:
        numero = "51" + solo
    else:
        numero = solo
    return f"https://wa.me/{numero}?text={quote(texto, safe='')}"


def armar_telefono(prefijo, numero):
    """Une el código de país con el número sin duplicar el código ni dejar el 0 inicial.
    Ej.: (+51, '987654321') -> '+51987654321'; (+51, '0987654321') -> '+51987654321'."""
    cod = "".join(ch for ch in str(prefijo or "") if ch.isdigit())
    dig = "".join(ch for ch in str(numero or "") if ch.isdigit())
    if not dig:
        return None
    if cod:
        if dig.startswith(cod) and len(dig) > len(cod) + 5:
            dig = dig[len(cod):]
        if cod == "51" and len(dig) == 10 and dig.startswith("0"):
            dig = dig[1:]
        return f"+{cod}{dig}"[:15]
    # Sin prefijo: si el número ya trae código (más de 9 dígitos), se conserva
    return (f"+{dig}" if len(dig) > 9 else dig)[:15]


def generar_comprobante_pdf(tipo_comprobante, numero_comprobante, fecha, cliente_nombre,
                            documento="", tipo_documento="", razon_social="",
                            direccion_fiscal="", productos=None, total_venta=0.0):
    """Genera el PDF del comprobante (boleta/factura/nota) y devuelve los bytes.

    Se usa para adjuntarlo al correo del comprobante. Mismo estilo que la ruta
    /comprobante/<id>/pdf (reportlab) pero soporta varios productos, porque un
    pedido del carrito puede tener más de un ítem.
    """
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    productos = productos or []
    titulo_comp = {
        "boleta": "BOLETA DE VENTA ELECTRÓNICA",
        "factura": "FACTURA ELECTRÓNICA",
        "nota": "NOTA DE VENTA",
    }.get(tipo_comprobante, "COMPROBANTE DE VENTA")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    estilos = getSampleStyleSheet()
    elementos = []

    elementos.append(Paragraph("LIBRERÍA SALESIANA DON BOSCO", estilos['Title']))
    elementos.append(Paragraph(f"<b>{titulo_comp}</b> N° {numero_comprobante}", estilos['Heading2']))
    elementos.append(Spacer(1, 8))

    titulo_doc = tipo_documento or ("RUC" if tipo_comprobante == "factura"
                                    else ("DNI" if documento else "No informado"))
    fecha_txt = fecha.strftime('%d/%m/%Y %H:%M') if hasattr(fecha, "strftime") else str(fecha)
    datos = [
        ["Fecha de emisión", fecha_txt],
        ["Cliente", cliente_nombre or "Consumidor Final"],
        [f"Documento ({titulo_doc})", documento or "—"],
    ]
    if razon_social:
        datos.append(["Razón social", razon_social])
    if direccion_fiscal:
        datos.append(["Dirección fiscal", direccion_fiscal])
    cabecera = Table(datos, colWidths=[55*mm, 115*mm])
    cabecera.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#EEF2FF')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
    ]))
    elementos.append(cabecera)
    elementos.append(Spacer(1, 12))

    # Detalle de productos
    filas = [["Producto", "Cant.", "P. Unit.", "Total"]]
    for p in productos:
        cantidad = int(p.get('cantidad', 1) or 1)
        precio = float(p.get('precio_unitario', p.get('precio', 0)) or 0)
        total_linea = float(p.get('total', precio * cantidad) or 0)
        filas.append([str(p.get('nombre', '')), str(cantidad),
                      f"S/ {precio:.2f}", f"S/ {total_linea:.2f}"])
    filas.append(["", "", "TOTAL", f"S/ {float(total_venta or 0):.2f}"])
    detalle = Table(filas, colWidths=[95*mm, 18*mm, 27*mm, 30*mm])
    detalle.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F0FDF4')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (2, -1), (3, -1), colors.HexColor('#16a34a')),
    ]))
    elementos.append(detalle)
    elementos.append(Spacer(1, 12))

    # Autorización SUNAT simulada (mismo criterio que /comprobante/<id>/pdf)
    codigo_autorizacion = f"{numero_comprobante} | {secrets.token_hex(8).upper()}"
    autorizacion = Table([["AUTORIZACIÓN SUNAT (SIMULADA)"], [codigo_autorizacion]], colWidths=[170*mm])
    autorizacion.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#16A34A')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDF4')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    elementos.append(autorizacion)
    elementos.append(Spacer(1, 8))
    elementos.append(Paragraph("<small>Este es un comprobante de venta electrónico válido. ¡Gracias por su compra!</small>", estilos['Italic']))

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()


def enviar_comprobante_email(destinatario, cliente_nombre, tipo_comprobante, numero_comprobante, fecha, productos, total_venta, documento="", tipo_documento="", razon_social="", direccion_fiscal=""):
    """Envía el comprobante (factura/boleta) por correo con estructura profesional de documento SUNAT."""
    try:
        import smtplib
        import html
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_server = EMAIL_HOST
        smtp_port = EMAIL_PORT
        smtp_user = EMAIL_USER
        smtp_password = EMAIL_PASSWORD

        if not destinatario or '@' not in destinatario:
            print(f"❌ Email inválido: {destinatario}")
            return False

        es_factura = tipo_comprobante == "factura"
        es_nota = tipo_comprobante == "nota"
        if es_factura:
            titulo = "FACTURA DE VENTA ELECTRÓNICA"
            asunto = f"🧾 FACTURA ELECTRÓNICA N° {numero_comprobante}"
        elif es_nota:
            titulo = "NOTA DE VENTA"
            asunto = f"📝 NOTA DE VENTA N° {numero_comprobante}"
        else:
            titulo = "BOLETA DE VENTA ELECTRÓNICA"
            asunto = f"📄 BOLETA DE VENTA ELECTRÓNICA N° {numero_comprobante}"

        e = html.escape
        cliente_mostrar = (cliente_nombre or "").strip() or "Consumidor Final"
        tipo_doc = tipo_documento or ("RUC" if es_factura else ("DNI" if documento else ("Sin documento" if es_nota else "")))
        doc_val = documento if documento else "—"

        # --- Panel de información (izq: fechas/tipo, der: cliente/documento) ---
        info_izq = f"""
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;">
                <div style="font-size:10px;letter-spacing:1px;color:#64748b;text-transform:uppercase;margin-bottom:2px;">Fecha de emisión</div>
                <div style="font-size:14px;font-weight:700;color:#0f172a;">{e(fecha.strftime('%d/%m/%Y %H:%M:%S'))}</div>
                <div style="font-size:10px;letter-spacing:1px;color:#64748b;text-transform:uppercase;margin:10px 0 2px;">Tipo de documento</div>
                <div style="font-size:13px;font-weight:600;color:#0f172a;">{titulo}</div>
                <div style="font-size:12px;color:#64748b;">N° {e(numero_comprobante)}</div>
            </div>"""

        info_der = f"""
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;">
                <div style="font-size:10px;letter-spacing:1px;color:#64748b;text-transform:uppercase;margin-bottom:2px;">Cliente</div>
                <div style="font-size:14px;font-weight:700;color:#0f172a;">{e(cliente_mostrar)}</div>
                <div style="font-size:10px;letter-spacing:1px;color:#64748b;text-transform:uppercase;margin:10px 0 2px;">Documento ({e(tipo_doc) if tipo_doc else 'No informado'})</div>
                <div style="font-size:14px;font-weight:700;color:#0f172a;">{e(doc_val)}</div>"""
        if es_factura and razon_social:
            info_der += f"""
                <div style="font-size:10px;letter-spacing:1px;color:#64748b;text-transform:uppercase;margin:10px 0 2px;">Razón social</div>
                <div style="font-size:13px;font-weight:600;color:#0f172a;">{e(razon_social)}</div>"""
        if es_factura and direccion_fiscal:
            info_der += f"""
                <div style="font-size:10px;letter-spacing:1px;color:#64748b;text-transform:uppercase;margin:10px 0 2px;">Dirección fiscal</div>
                <div style="font-size:13px;color:#0f172a;">{e(direccion_fiscal)}</div>"""
        info_der += "</div>"

        # --- Tabla de productos ---
        filas = ""
        for i, p in enumerate(productos):
            nombre = e(str(p['nombre']))
            cantidad = p.get('cantidad', 1)
            precio = float(p.get('precio_unitario', p.get('precio', 0)))
            total_linea = float(p.get('total', precio * cantidad))
            fondo = "background:#ffffff;" if i % 2 == 0 else "background:#f8fafc;"
            filas += f"""
                        <tr style="{fondo}">
                            <td style="padding:10px 12px;border-bottom:1px solid #eef2f7;color:#334155;font-size:13px;">{nombre}</td>
                            <td style="padding:10px 12px;border-bottom:1px solid #eef2f7;text-align:center;color:#475569;font-size:13px;">{cantidad}</td>
                            <td style="padding:10px 12px;border-bottom:1px solid #eef2f7;text-align:right;color:#475569;font-size:13px;">S/. {precio:,.2f}</td>
                            <td style="padding:10px 12px;border-bottom:1px solid #eef2f7;text-align:right;color:#0f172a;font-size:13px;font-weight:600;">S/. {total_linea:,.2f}</td>
                        </tr>"""

        total_int = int(total_venta)
        centimos = int(round((total_venta - total_int) * 100))
        son = f"{numero_a_letras(total_int)} soles con {centimos:02d}/100"

        if es_factura:
            nota_validez = "Este documento es válido para efectos de crédito fiscal ante SUNAT."
        else:
            nota_validez = "Válido como boleta de venta electrónica. No es documento para crédito fiscal."

        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = destinatario
        msg['Subject'] = asunto

        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>{asunto}</title></head>
        <body style="margin:0;padding:0;background:#eef2f7;font-family:'Segoe UI',Arial,sans-serif;">
            <div style="max-width:660px;margin:24px auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;">

                <!-- CABECERA -->
                <div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:26px 30px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="vertical-align:middle;">
                                <table cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td style="font-size:34px;padding-right:12px;">📚</td>
                                        <td>
                                            <div style="font-size:19px;font-weight:800;letter-spacing:.5px;color:#fff;">LIBRERÍA SALESIANA</div>
                                            <div style="font-size:19px;font-weight:800;letter-spacing:.5px;color:#fff;">DON BOSCO</div>
                                            <div style="font-size:11px;opacity:.8;color:#e0e7ff;margin-top:2px;">Comprobante de venta electrónico</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                            <td style="text-align:right;vertical-align:middle;">
                                <div style="display:inline-block;border:2px solid rgba(255,255,255,.75);border-radius:10px;padding:8px 18px;text-align:center;">
                                    <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#e0e7ff;">{titulo}</div>
                                    <div style="font-size:20px;font-weight:900;color:#fff;letter-spacing:1px;">N° {e(numero_comprobante)}</div>
                                </div>
                            </td>
                        </tr>
                    </table>
                </div>

                <!-- INFORMACIÓN -->
                <table width="100%" cellpadding="0" cellspacing="0" style="padding:20px 26px 6px;">
                    <tr>
                        <td style="padding:8px;vertical-align:top;width:50%;">{info_izq}</td>
                        <td style="padding:8px;vertical-align:top;width:50%;">{info_der}</td>
                    </tr>
                </table>

                <!-- PRODUCTOS -->
                <table width="100%" cellpadding="0" cellspacing="0" style="padding:10px 26px 0;">
                    <tr>
                        <td>
                            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                                <tr style="background:#1e3a8a;">
                                    <th style="padding:10px 12px;color:#fff;font-size:11px;letter-spacing:1px;text-transform:uppercase;text-align:left;">Producto</th>
                                    <th style="padding:10px 12px;color:#fff;font-size:11px;letter-spacing:1px;text-transform:uppercase;text-align:center;">Cant.</th>
                                    <th style="padding:10px 12px;color:#fff;font-size:11px;letter-spacing:1px;text-transform:uppercase;text-align:right;">P. Unitario</th>
                                    <th style="padding:10px 12px;color:#fff;font-size:11px;letter-spacing:1px;text-transform:uppercase;text-align:right;">Total</th>
                                </tr>
                                {filas}
                                <tr style="background:#f0fdf4;">
                                    <td colspan="3" style="padding:14px 12px;text-align:right;color:#0f172a;font-size:14px;font-weight:700;text-transform:uppercase;">Total</td>
                                    <td style="padding:14px 12px;text-align:right;color:#16a34a;font-size:19px;font-weight:900;">S/. {total_venta:,.2f}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                <!-- SON: -->
                <table width="100%" cellpadding="0" cellspacing="0" style="padding:4px 38px 0;">
                    <tr>
                        <td style="text-align:right;color:#64748b;font-size:12px;font-style:italic;">SON: {e(son.upper())}</td>
                    </tr>
                </table>

                <!-- NOTA DE VALIDEZ -->
                <table width="100%" cellpadding="0" cellspacing="0" style="padding:14px 26px;">
                    <tr>
                        <td style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:12px 16px;color:#1e3a8a;font-size:12px;text-align:center;">{nota_validez}</td>
                    </tr>
                </table>

                <!-- CIERRE -->
                <table width="100%" cellpadding="0" cellspacing="0" style="padding:0 26px 18px;">
                    <tr>
                        <td style="text-align:center;padding:10px 14px;color:#334155;">
                            <div style="font-size:15px;font-weight:800;color:#1d4ed8;">✨ ¡Gracias por su compra! ✨</div>
                            <div style="font-size:12px;color:#64748b;margin-top:4px;">Comprobante de venta electrónico válido</div>
                        </td>
                    </tr>
                </table>

                <!-- PIE -->
                <div style="background:#f1f5f9;padding:16px 26px;text-align:center;font-size:11px;color:#64748b;">
                    <div style="font-weight:700;color:#334155;">Librería Salesiana Don Bosco | Todos los derechos reservados</div>
                    <div style="margin-top:3px;">📧 ventas@librospe.alwaysdata.net &nbsp;|&nbsp; 📞 (01) 123-4567</div>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))

        # Adjuntar el comprobante en PDF (además del detalle en el cuerpo del correo).
        # Así el cliente recibe "el documento" descargable y no solo el HTML.
        try:
            from email.mime.application import MIMEApplication
            pdf_bytes = generar_comprobante_pdf(
                tipo_comprobante=tipo_comprobante,
                numero_comprobante=numero_comprobante,
                fecha=fecha,
                cliente_nombre=cliente_nombre,
                documento=documento,
                tipo_documento=tipo_documento,
                razon_social=razon_social,
                direccion_fiscal=direccion_fiscal,
                productos=productos,
                total_venta=total_venta,
            )
            prefijo_archivo = {"factura": "Factura", "nota": "NotaVenta"}.get(tipo_comprobante, "Boleta")
            numero_limpio = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in str(numero_comprobante))
            nombre_pdf = f"{prefijo_archivo}_{numero_limpio}.pdf"
            adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
            adjunto.add_header("Content-Disposition", "attachment", filename=nombre_pdf)
            msg.attach(adjunto)
            print(f"📎 PDF adjuntado: {nombre_pdf}")
        except Exception as e:
            print(f"⚠️ No se pudo adjuntar el PDF: {e}")

        print(f"📧 Enviando a {destinatario}...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        print(f"✅ Correo enviado a {destinatario}")
        return True

    except Exception as e:
        print(f"❌ Error al enviar correo: {e}")
        return False



def enviar_entrega_email(cliente_obj, pedido):
    """Envía el correo de entrega con la constancia y la solicitud de confirmación de recepción."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        destinatario = cliente_obj.correo
        if not destinatario or '@' not in destinatario:
            print(f"❌ Email inválido para entrega: {destinatario}")
            return False

        nombre = f"{cliente_obj.nombres or ''} {cliente_obj.apellidos or ''}".strip() or destinatario
        url_pedidos = url_for("mis_pedidos", _external=True)

        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = destinatario
        msg['Subject'] = f"🚚 Tu pedido N° {pedido.id} fue entregado - Confirma tu recepción"

        html = f"""
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f8f9fa; }}
                .card {{ max-width: 560px; margin: 30px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.08); }}
                .header {{ background: linear-gradient(135deg, #16a34a, #4ade80); color: white; padding: 26px; text-align: center; }}
                .content {{ padding: 24px; color: #333; }}
                .btn {{ display: inline-block; background: #16a34a; color: #fff; padding: 12px 26px; border-radius: 8px;
                        text-decoration: none; font-weight: bold; margin: 14px 0; }}
                .footer {{ background: #e9ecef; padding: 14px; text-align: center; font-size: 12px; color: #6c757d; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="header">
                    <h2>✅ ¡Tu pedido fue entregado!</h2>
                    <p>Pedido N° {pedido.id}</p>
                </div>
                <div class="content">
                    <p>Hola <strong>{nombre}</strong>,</p>
                    <p>Tu pedido <strong>N° {pedido.id}</strong> fue <strong>entregado</strong> el
                       <strong>{pedido.fecha_entrega.strftime('%d/%m/%Y %H:%M') if pedido.fecha_entrega else 'hoy'}</strong>
                       y fue recibido por <strong>{pedido.nombre_recibe or 'la persona indicada'}</strong>.</p>
                    <p>Para completar el proceso, confírmanos que lo recibiste:</p>
                    <p style="text-align:center;">
                        <a class="btn" href="{url_pedidos}">✅ Confirmo que recibí mi pedido</a>
                    </p>
                    <p>Si tienes algún problema con tu pedido, escríbenos respondiendo este correo.</p>
                </div>
                <div class="footer">
                    <p>Librería Salesiana Don Bosco | Todos los derechos reservados</p>
                </div>
            </div>
        </body></html>
        """
        msg.attach(MIMEText(html, 'html'))

        print(f"📧 Enviando correo de entrega a {destinatario}...")
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Correo de entrega enviado a {destinatario}")
        return True
    except Exception as e:
        print(f"❌ Error al enviar correo de entrega: {e}")
        return False

@app.route("/")
def inicio():
    return render_template("index.html")


# ===============================
# PWA - MANIFIESTO Y SERVICE WORKER
# ===============================

@app.route("/manifest.webmanifest")
def pwa_manifest():
    resp = app.send_static_file("manifest.webmanifest")
    resp.headers["Content-Type"] = "application/manifest+json"
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@app.route("/sw.js")
def pwa_service_worker():
    resp = app.send_static_file("sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ===============================
# CONTEXT PROCESSOR - CATEGORÍAS
# ===============================

@app.context_processor
def inject_categorias():
    """Inyecta categorías en todas las plantillas"""
    try:
        categorias = Categoria.query.filter_by(activo=True).all()
        return dict(categorias=categorias)
    except:
        return dict(categorias=[])

@app.route("/login", methods=["GET", "POST"])
def login():
    try:
        ip_cliente = obtener_ip_cliente()
        limpiar_bloqueos_expirados()
        
        if verificar_bloqueo_ip(ip_cliente):
            flash("⛔ ACCESO DENEGADO: Esta IP ha sido bloqueada por múltiples intentos fallidos de diferentes usuarios. Espera 10 minutos.", "danger")
            return render_template("login.html")
        
        if request.method == "POST":
            correo = request.form.get("correo", "").strip()
            clave = request.form.get("clave", "")
            
            if not correo or not clave:
                flash("❌ Ingresa correo y contraseña", "danger")
                return render_template("login.html")
            
            if verificar_bloqueo_email(correo):
                flash("⛔ CUENTA BLOQUEADA: Has agotado tus 3 intentos. Espera 10 minutos.", "danger")
                return render_template("login.html")
            
            if verificar_bloqueo_ip(ip_cliente):
                flash("⛔ ACCESO DENEGADO: Esta IP ha sido bloqueada. Espera 10 minutos.", "danger")
                return render_template("login.html")
            
            try:
                usuario = UsuarioSistema.query.filter_by(correo=correo).first()
                
                if not usuario:
                    resultado = registrar_intento_fallido(correo, ip_cliente, es_cliente=False)
                    flash("❌ Acceso denegado. Este correo no está registrado en el sistema.", "danger")
                    if resultado.get("bloqueado") and resultado["tipo"] == "ip":
                        flash(f"⛔ {resultado['mensaje']}", "danger")
                        return redirect(url_for("login"))
                    return render_template("login.html")
                
                # ============================================
                # VERIFICAR SI EL USUARIO SISTEMA ESTÁ BLOQUEADO
                # ============================================
                # 1. Verificar bloqueo manual en tabla 'bloqueos'
                bloqueo = db.session.execute(text("""
                    SELECT id, motivo, fecha_bloqueo 
                    FROM bloqueos 
                    WHERE usuario_sistema_id = :usuario_id 
                    AND tipo_usuario = 'sistema' 
                    AND estado = 1
                """), {"usuario_id": usuario.id}).mappings().first()
                
                if bloqueo:
                    flash(f"⛔ CUENTA BLOQUEADA", "danger")
                    flash(f"📝 Motivo: {bloqueo['motivo'] or 'No especificado'}", "warning")
                    flash(f"📅 Fecha de bloqueo: {bloqueo['fecha_bloqueo'].strftime('%d/%m/%Y %H:%M') if bloqueo['fecha_bloqueo'] else 'N/A'}", "info")
                    flash("🔒 Contacta al administrador para desbloquear tu cuenta.", "warning")
                    return render_template("login.html")
                
                # 2. Verificar bloqueo automático en 'intentos_login'
                bloqueo_auto = db.session.execute(text("""
                    SELECT email_bloqueado, intentos 
                    FROM intentos_login 
                    WHERE email = :email 
                    AND email_bloqueado IS NOT NULL 
                    AND email_bloqueado > NOW()
                """), {"email": correo}).mappings().first()
                
                if bloqueo_auto:
                    flash(f"⛔ CUENTA BLOQUEADA TEMPORALMENTE", "danger")
                    flash(f"📝 Motivo: Bloqueo automático por {bloqueo_auto['intentos']} intentos fallidos de login", "warning")
                    flash(f"⏳ Tiempo restante: {(bloqueo_auto['email_bloqueado'] - datetime.now()).seconds // 60} minutos", "info")
                    flash("🔄 Espera a que se desbloquee automáticamente o contacta al administrador.", "warning")
                    return render_template("login.html")
                # ============================================
                
                if bcrypt.check_password_hash(usuario.clave, clave):
                    limpiar_intentos_exitosos(correo, ip_cliente)
                    session["usuario_id"] = usuario.id
                    session["rol"] = usuario.rol
                    session["nombre"] = usuario.nombres
                    if usuario.debe_cambiar_clave:
                        flash("⚠️ Debes cambiar tu contraseña antes de continuar", "warning")
                        return redirect(url_for("cambiar_clave"))
                    flash(f"✅ Bienvenido {usuario.nombres}", "success")
                    return redirect(url_for("productos"))
                else:
                    resultado = registrar_intento_fallido(correo, ip_cliente, es_cliente=False)
                    if resultado.get("bloqueado"):
                        flash(f"⛔ {resultado['mensaje']}", "danger")
                        if resultado["tipo"] == "ip":
                            flash("⚠️ A partir de ahora, NINGÚN usuario podrá iniciar sesión desde esta IP durante 10 minutos.", "warning")
                            return redirect(url_for("login"))
                    else:
                        intentos = resultado.get("intentos_restantes", 0)
                        if intentos > 0 and intentos != 999:
                            flash(f"❌ Contraseña incorrecta. Te quedan {intentos} intento(s).", "danger")
                        else:
                            flash("❌ Contraseña incorrecta. Próximo intento bloqueará la cuenta.", "warning")
                    return render_template("login.html")
                    
            except Exception as e:
                print(f"❌ Error en login POST: {e}")
                import traceback
                traceback.print_exc()
                flash("❌ Error al procesar el login", "danger")
                return render_template("login.html")
        
        return render_template("login.html")
        
    except Exception as e:
        print(f"❌ ERROR EN LOGIN: {e}")
        import traceback
        traceback.print_exc()
        flash(f"❌ Error interno del servidor", "danger")
        return render_template("login.html")

@app.route("/login-cliente", methods=["GET", "POST"])
def login_cliente():
    ip_cliente = obtener_ip_cliente()
    limpiar_bloqueos_expirados()
    
    # Variables para el template
    template_data = {
        "bloqueo_permanente": None,
        "bloqueo_temporal": False,
        "minutos_restantes": 0,
        "intentos_restantes": None,
        "intentos_totales": None,
        "intentos_para_permanente": None
    }
    
    if verificar_bloqueo_ip(ip_cliente):
        flash("⛔ ACCESO DENEGADO: Esta IP ha sido bloqueada. Espera 10 minutos.", "danger")
        return render_template("login_cliente.html", **template_data)
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        clave = request.form.get("clave", "")
        
        if not email or not clave:
            flash("❌ Ingresa email y contraseña", "danger")
            return render_template("login_cliente.html", **template_data)
        
        # ============================================
        # VERIFICAR BLOQUEO DE EMAIL (TEMPORAL O PERMANENTE)
        # ============================================
        if verificar_bloqueo_email(email):
            cliente_tmp = _obtener_cliente_por_correo(email)
            if cliente_tmp:
                bloqueo_permanente = db.session.execute(text("""
                    SELECT id, motivo, permanente 
                    FROM bloqueos 
                    WHERE cliente_id = :cliente_id 
                    AND tipo_usuario = 'cliente' 
                    AND estado = 1 
                    AND permanente = 1
                """), {"cliente_id": cliente_tmp.id}).mappings().first()
                
                if bloqueo_permanente:
                    flash("⛔ CUENTA BLOQUEADA PERMANENTEMENTE", "danger")
                    flash(f"📝 Motivo: {bloqueo_permanente['motivo'] or '5 intentos fallidos de login'}", "warning")
                    flash("🔒 Contacta al administrador para desbloquear tu cuenta.", "warning")
                    template_data["bloqueo_permanente"] = {
                        "motivo": bloqueo_permanente['motivo'] or "Has excedido el número máximo de intentos permitidos."
                    }
                else:
                    # Bloqueo temporal
                    registro = IntentosLogin.query.filter_by(email=email).first()
                    if registro and registro.email_bloqueado:
                        minutos_restantes = (registro.email_bloqueado - datetime.now()).seconds // 60
                        flash("⛔ CUENTA BLOQUEADA TEMPORALMENTE", "danger")
                        flash(f"⏳ Has agotado tus 3 intentos. Espera {minutos_restantes} minutos para volver a intentar.", "warning")
                        template_data["bloqueo_temporal"] = True
                        template_data["minutos_restantes"] = minutos_restantes
            else:
                flash("⛔ CUENTA BLOQUEADA", "danger")
                flash("⏳ Espera 10 minutos para volver a intentar.", "warning")
            
            return render_template("login_cliente.html", **template_data)
        
        if verificar_bloqueo_ip(ip_cliente):
            flash("⛔ ACCESO DENEGADO: Esta IP ha sido bloqueada. Espera 10 minutos.", "danger")
            return render_template("login_cliente.html", **template_data)
        
        cliente = _obtener_cliente_por_correo(email)
        
        if not cliente:
            resultado = registrar_intento_fallido(email, ip_cliente, es_cliente=True)
            flash("❌ Este correo no está registrado. ¿Deseas crear una cuenta nueva?", "warning")
            flash("💡 Haz clic en 'Registrarme' para crear una cuenta.", "info")
            if resultado.get("bloqueado") and resultado["tipo"] == "ip":
                flash(f"⛔ {resultado['mensaje']}", "danger")
                return redirect(url_for("login_cliente"))
            return render_template("login_cliente.html", **template_data)
        
        # ============================================
        # VERIFICAR BLOQUEOS ACTIVOS DEL CLIENTE
        # ============================================
        # 1. Verificar bloqueo permanente
        bloqueo_permanente = db.session.execute(text("""
            SELECT id, motivo, permanente, fecha_bloqueo
            FROM bloqueos 
            WHERE cliente_id = :cliente_id 
            AND tipo_usuario = 'cliente' 
            AND estado = 1 
            AND permanente = 1
        """), {"cliente_id": cliente.id}).mappings().first()
        
        if bloqueo_permanente:
            flash("⛔ CUENTA BLOQUEADA PERMANENTEMENTE", "danger")
            flash(f"📝 Motivo: {bloqueo_permanente['motivo'] or '5 intentos fallidos de login'}", "warning")
            flash(f"📅 Fecha de bloqueo: {bloqueo_permanente['fecha_bloqueo'].strftime('%d/%m/%Y %H:%M') if bloqueo_permanente['fecha_bloqueo'] else 'N/A'}", "info")
            flash("🔒 Contacta al administrador para desbloquear tu cuenta.", "warning")
            template_data["bloqueo_permanente"] = {
                "motivo": bloqueo_permanente['motivo'] or "Has excedido el número máximo de intentos permitidos."
            }
            return render_template("login_cliente.html", **template_data)
        
        # 2. Verificar bloqueo temporal (debe estar en intentos_login)
        registro_intentos = IntentosLogin.query.filter_by(email=email).first()
        if registro_intentos and registro_intentos.email_bloqueado and registro_intentos.email_bloqueado > datetime.now():
            minutos_restantes = (registro_intentos.email_bloqueado - datetime.now()).seconds // 60
            flash("⛔ CUENTA BLOQUEADA TEMPORALMENTE", "danger")
            flash(f"⏳ Has agotado tus 3 intentos. Espera {minutos_restantes} minutos para volver a intentar.", "warning")
            template_data["bloqueo_temporal"] = True
            template_data["minutos_restantes"] = minutos_restantes
            return render_template("login_cliente.html", **template_data)
        
        # ============================================
        # VERIFICAR ESTADO ACTIVO (admin desactivó)
        # ============================================
        if getattr(cliente, "estado", 1) == 0 or str(getattr(cliente, "estado", "1")) == "0":
            flash("❌ Cuenta desactivada por el administrador. Contacta soporte.", "danger")
            return render_template("login_cliente.html", **template_data)

        # ============================================
        # VERIFICAR CONTRASEÑA
        # ============================================
        if bcrypt.check_password_hash(cliente.clave, clave):
            # Login exitoso - limpiar intentos
            limpiar_intentos_exitosos(email, ip_cliente)
            
            # Si tenía un bloqueo temporal en tabla bloqueos, desactivarlo
            db.session.execute(text("""
                UPDATE bloqueos 
                SET estado = 0, fecha_desbloqueo = NOW() 
                WHERE cliente_id = :cliente_id 
                AND tipo_usuario = 'cliente' 
                AND permanente = 0 
                AND estado = 1
            """), {"cliente_id": cliente.id})
            db.session.commit()
            
            session["cliente_id"] = cliente.id
            session["cliente_nombres"] = cliente.nombres
            session["cliente_apellidos"] = cliente.apellidos
            session["cliente_correo"] = cliente.correo
            session["cliente_telefono"] = cliente.telefono
            session["cliente_direccion"] = cliente.direccion
            session["cliente_dni"] = cliente.dni
            flash(f"✅ ¡Bienvenido {cliente.nombres}!", "success")
            return redirect("/catalogo")
        else:
            # ============================================
            # REGISTRAR INTENTO FALLIDO
            # ============================================
            resultado = registrar_intento_fallido(email, ip_cliente, es_cliente=True)
            
            # Actualizar template_data con los intentos
            template_data["intentos_restantes"] = resultado.get("intentos_restantes", 0)
            template_data["intentos_totales"] = resultado.get("intentos_totales", 0)
            template_data["intentos_para_permanente"] = resultado.get("intentos_para_bloqueo_permanente", 5)
            
            if resultado.get("bloqueado"):
                if resultado["tipo"] == "permanente":
                    flash("⛔ ¡CUENTA BLOQUEADA PERMANENTEMENTE!", "danger")
                    flash("📝 Motivo: 5 intentos fallidos de login", "warning")
                    flash("🔒 Contacta al administrador para desbloquear tu cuenta.", "warning")
                    template_data["bloqueo_permanente"] = {
                        "motivo": "Has excedido el número máximo de intentos permitidos (5 fallos)."
                    }
                elif resultado["tipo"] == "email":
                    flash(f"⛔ {resultado['mensaje']}", "danger")
                    flash("⏳ Espera 10 minutos antes de volver a intentar.", "warning")
                    # Verificar si hay minutos restantes
                    registro = IntentosLogin.query.filter_by(email=email).first()
                    if registro and registro.email_bloqueado:
                        minutos_restantes = (registro.email_bloqueado - datetime.now()).seconds // 60
                        template_data["bloqueo_temporal"] = True
                        template_data["minutos_restantes"] = minutos_restantes
                elif resultado["tipo"] == "ip":
                    flash(f"⛔ {resultado['mensaje']}", "danger")
                    flash("⚠️ NINGÚN cliente podrá iniciar sesión desde esta IP durante 10 minutos.", "warning")
                else:
                    flash(f"⛔ {resultado['mensaje']}", "danger")
            else:
                intentos_restantes = resultado.get("intentos_restantes", 0)
                intentos_totales = resultado.get("intentos_totales", 0)
                intentos_para_permanente = resultado.get("intentos_para_bloqueo_permanente", 5)
                
                if intentos_restantes > 0 and intentos_restantes != 999:
                    if intentos_restantes <= 1:
                        flash(f"⚠️ ¡ATENCIÓN! Contraseña incorrecta. Te queda {intentos_restantes} intento para bloqueo TEMPORAL.", "danger")
                        flash(f"💡 Si fallas 2 veces más (total {intentos_totales + 2} de 5), tu cuenta será BLOQUEADA PERMANENTEMENTE.", "warning")
                    else:
                        flash(f"❌ Contraseña incorrecta. Te quedan {intentos_restantes} intentos para bloqueo TEMPORAL.", "danger")
                        flash(f"ℹ️ Intentos totales: {intentos_totales} de 5. Si llegas a 5, tu cuenta será BLOQUEADA PERMANENTEMENTE.", "info")
                else:
                    # Mostrar información del progreso hacia bloqueo permanente
                    if intentos_totales >= 4:
                        flash(f"⚠️ ¡ÚLTIMO INTENTO! Contraseña incorrecta. Si fallas una vez más (5 de 5), tu cuenta será BLOQUEADA PERMANENTEMENTE.", "danger")
                    else:
                        flash(f"❌ Contraseña incorrecta. Próximo intento (3 de 3) bloqueará la cuenta TEMPORALMENTE por 10 minutos.", "warning")
                        flash(f"ℹ️ Intentos totales: {intentos_totales} de 5. Con 5 fallos, bloqueo PERMANENTE.", "info")
            
            return render_template("login_cliente.html", **template_data)
    
    # GET - Mostrar intentos actuales si existen
    email_cookie = request.cookies.get('email_actual')
    if email_cookie:
        registro = IntentosLogin.query.filter_by(email=email_cookie).first()
        if registro and not registro.email_bloqueado:
            template_data["intentos_restantes"] = 3 - registro.intentos
            template_data["intentos_totales"] = registro.intentos_totales
            template_data["intentos_para_permanente"] = 5 - registro.intentos_totales
    
    return render_template("login_cliente.html", **template_data)

@app.route("/bloqueos-sistema")
@login_required
def ver_bloqueos_sistema():
    if session.get("rol") != "administrador":
        flash("❌ Solo administradores pueden ver bloqueos", "danger")
        return redirect(url_for("dashboard"))
    
    try:
        # ============================================
        # 1. BLOQUEOS MANUALES DE USUARIOS SISTEMA
        # ============================================
        bloqueos_sistema = db.session.execute(text("""
            SELECT 
                b.id,
                b.usuario_sistema_id,
                b.motivo,
                b.fecha_bloqueo,
                b.bloqueado_por,
                b.estado,
                u.correo AS usuario_correo,
                u.nombres AS usuario_nombres,
                u.apellidos AS usuario_apellidos,
                u.rol AS usuario_rol,
                CONCAT(bloq.nombres, ' ', bloq.apellidos) AS bloqueado_por_nombre
            FROM bloqueos b
            LEFT JOIN usuarios_sistema u ON b.usuario_sistema_id = u.id
            LEFT JOIN usuarios_sistema bloq ON b.bloqueado_por = bloq.id
            WHERE b.tipo_usuario = 'sistema' AND b.estado = 1
            ORDER BY b.fecha_bloqueo DESC
        """)).mappings().all()
        
        # ============================================
        # 2. BLOQUEOS AUTOMÁTICOS DE USUARIOS SISTEMA
        # ============================================
        intentos_sistema = db.session.execute(text("""
            SELECT 
                i.id,
                i.email,
                i.intentos,
                i.email_bloqueado,
                i.ip,
                u.id AS usuario_id,
                u.nombres AS usuario_nombres,
                u.apellidos AS usuario_apellidos,
                u.rol AS usuario_rol
            FROM intentos_login i
            JOIN usuarios_sistema u ON i.email = u.correo
            WHERE i.email_bloqueado IS NOT NULL AND i.email_bloqueado > NOW()
            ORDER BY i.email_bloqueado DESC
        """)).mappings().all()
        
        # ============================================
        # 3. UNIFICAR
        # ============================================
        bloqueos_lista = []
        
        # Manuales
        for b in bloqueos_sistema:
            bloqueo_dict = {
                'id_bloqueo': b['id'],
                'tipo': 'Sistema',
                'nombre_completo': f"{b['usuario_nombres'] or ''} {b['usuario_apellidos'] or ''}".strip(),
                'email': b['usuario_correo'],
                'rol': b['usuario_rol'],
                'motivo': b['motivo'] or 'Sin motivo',
                'fecha_bloqueo': b['fecha_bloqueo'],
                'bloqueado_por': b['bloqueado_por_nombre'] or 'Sistema',
                'origen': 'Manual',
                'tipo_origen': 'bloqueos',
                'id_usuario': b['usuario_sistema_id']
            }
            bloqueos_lista.append(bloqueo_dict)
        
        # Automáticos
        for i in intentos_sistema:
            bloqueo_dict = {
                'id_bloqueo': i['id'],
                'tipo': 'Sistema',
                'nombre_completo': f"{i['usuario_nombres'] or ''} {i['usuario_apellidos'] or ''}".strip() or 'Desconocido',
                'email': i['email'],
                'rol': i['usuario_rol'],
                'motivo': f"Bloqueo automático por {i['intentos']} intentos fallidos de login",
                'fecha_bloqueo': i['email_bloqueado'],
                'bloqueado_por': 'Sistema',
                'origen': 'Automático',
                'tipo_origen': 'intentos_login',
                'id_usuario': i['usuario_id'],
                'ip': i['ip']
            }
            bloqueos_lista.append(bloqueo_dict)
        
        return render_template("bloqueos_sistema.html", bloqueos=bloqueos_lista)
        
    except Exception as e:
        print(f"❌ Error en bloqueos_sistema: {e}")
        flash(f"Error al cargar bloqueos: {e}", "danger")
        return render_template("bloqueos_sistema.html", bloqueos=[])

@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("✅ Sesión cerrada", "success")
    return redirect(url_for("login"))

@app.route("/usuarios/nuevo", methods=["GET", "POST"])
@login_required
@admin_required
def nuevo_usuario():
    if request.method == "POST":
        try:
            # Resolver rol_id a partir del nombre del rol (tabla roles)
            rol_nombre = {"administrador": "admin", "vendedor": "vendedor"}.get(
                request.form["rol"], request.form["rol"].lower()
            )
            rol_registro = db.session.execute(
                text("SELECT id FROM roles WHERE nombre = :n LIMIT 1"), {"n": rol_nombre}
            ).fetchone()
            if not rol_registro:
                flash("❌ Rol no válido", "danger")
                return redirect(url_for("nuevo_usuario"))

            doc_val = (request.form.get("documento") or "").strip()
            if not doc_val:
                flash("❌ El documento (DNI/CE) es obligatorio", "danger")
                return redirect(url_for("nuevo_usuario"))
            # Validación: DNI 8 dígitos, CE 9 caracteres
            if doc_val.isdigit():
                if len(doc_val) != 8:
                    flash("❌ DNI debe tener exactamente 8 dígitos", "danger")
                    return redirect(url_for("nuevo_usuario"))
            else:
                if len(doc_val) != 9:
                    flash("❌ CE debe tener 9 caracteres", "danger")
                    return redirect(url_for("nuevo_usuario"))
            clave = (request.form.get("clave") or "").strip()
            confirmar = (request.form.get("confirmar_clave") or "").strip()
            if not clave or len(clave) < 8:
                flash("❌ La contraseña debe tener al menos 8 caracteres", "danger")
                return redirect(url_for("nuevo_usuario"))
            if confirmar and clave != confirmar:
                flash("❌ Las contraseñas no coinciden", "danger")
                return redirect(url_for("nuevo_usuario"))
            # Si no hay confirmar (compatibilidad), usa clave
            clave_hash = bcrypt.generate_password_hash(clave).decode("utf-8")
            nuevo = UsuarioSistema(
                correo=request.form["correo"],
                nombres=request.form["nombres"],
                apellidos=request.form["apellidos"],
                rol=request.form["rol"],
                rol_id=rol_registro[0],
                documento=doc_val,
                debe_cambiar_clave=0,
                clave=clave_hash,
            )
            db.session.add(nuevo)
            db.session.commit()
            # Dual-write a microservicio usuarios (dueño) - asegura dato en librospe_ms_usuarios
            try:
                try:
                    eng_u = db.get_engine(bind="usuarios")
                except Exception:
                    eng_u = db.engines.get("usuarios") if hasattr(db, "engines") else None
                if eng_u is not None:
                    db.session.execute(text("""
                        INSERT INTO usuarios_sistema (id, correo, nombres, apellidos, clave, estado, rol_id, rol, documento)
                        VALUES (:id, :correo, :nombres, :apellidos, :clave, 1, :rol_id, :rol, :documento)
                        ON DUPLICATE KEY UPDATE nombres=VALUES(nombres), apellidos=VALUES(apellidos), correo=VALUES(correo)
                    """), {
                        "id": nuevo.id, "correo": nuevo.correo, "nombres": nuevo.nombres, "apellidos": nuevo.apellidos,
                        "clave": clave_hash, "rol_id": nuevo.rol_id, "rol": nuevo.rol, "documento": nuevo.documento
                    }, bind_arguments={"bind": eng_u})
                    db.session.commit()
            except Exception as e:
                print(f"WARN dual-write usuarios: {e}")
            registrar_auditoria("CREAR", "usuarios_sistema", f"Se creó el usuario {request.form['nombres']} {request.form['apellidos']} (rol: {request.form['rol']})")
            flash("✅ Usuario registrado correctamente", "success")
            return redirect(url_for("proveedores"))
        except Exception:
            db.session.rollback()
            flash("❌ Error: El correo ya existe", "danger")
            return redirect(url_for("nuevo_usuario"))
    return render_template("usuarios_sistema_form.html")

@app.route("/usuario/bloquear/<int:usuario_id>", methods=["POST"])
@login_required
def bloquear_usuario_sistema(usuario_id):
    """Bloquear un usuario del sistema"""
    if session.get("rol") != "administrador":
        flash("❌ No autorizado", "danger")
        return redirect(url_for("usuarios_sistema"))
    
    motivo = request.form.get("motivo", "Bloqueo manual por administrador")
    
    try:
        # Verificar si el usuario existe
        usuario = UsuarioSistema.query.get(usuario_id)
        if not usuario:
            flash("❌ Usuario no encontrado", "danger")
            return redirect(url_for("usuarios_sistema"))
        
        # Verificar si ya tiene un bloqueo activo
        existe = db.session.execute(text("""
            SELECT id FROM bloqueos 
            WHERE usuario_sistema_id = :usuario_id 
            AND tipo_usuario = 'sistema' 
            AND estado = 1
        """), {"usuario_id": usuario_id}).fetchone()
        
        if existe:
            flash("⚠️ El usuario ya está bloqueado", "warning")
            return redirect(url_for("usuarios_sistema"))
        
        # Crear bloqueo
        db.session.execute(text("""
            INSERT INTO bloqueos 
            (tipo_usuario, usuario_sistema_id, motivo, fecha_bloqueo, bloqueado_por, estado)
            VALUES ('sistema', :usuario_id, :motivo, NOW(), :admin_id, 1)
        """), {"usuario_id": usuario_id, "motivo": motivo, "admin_id": session["usuario_id"]})
        
        db.session.commit()
        flash(f"✅ Usuario {usuario.nombres} bloqueado exitosamente", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al bloquear: {e}", "danger")
    
    return redirect(url_for("usuarios_sistema"))


@app.route("/usuario/desbloquear/<int:usuario_id>", methods=["POST"])
@login_required
def desbloquear_usuario_sistema(usuario_id):
    """Desbloquear un usuario del sistema"""
    if session.get("rol") != "administrador":
        flash("❌ No autorizado", "danger")
        return redirect(url_for("usuarios_sistema"))
    
    try:
        # Buscar bloqueo activo
        bloqueo = db.session.execute(text("""
            SELECT id FROM bloqueos 
            WHERE usuario_sistema_id = :usuario_id 
            AND tipo_usuario = 'sistema' 
            AND estado = 1
        """), {"usuario_id": usuario_id}).fetchone()
        
        if bloqueo:
            # Desbloquear manual
            db.session.execute(text("""
                UPDATE bloqueos 
                SET estado = 0, 
                    fecha_desbloqueo = NOW(),
                    desbloqueado_por = :admin_id
                WHERE id = :bloqueo_id
            """), {"bloqueo_id": bloqueo[0], "admin_id": session["usuario_id"]})
            flash("✅ Usuario desbloqueado exitosamente", "success")
        else:
            # Verificar si tiene bloqueo automático en intentos_login
            usuario = UsuarioSistema.query.get(usuario_id)
            if usuario:
                db.session.execute(text("""
                    UPDATE intentos_login 
                    SET email_bloqueado = NULL, intentos = 0 
                    WHERE email = :email
                """), {"email": usuario.correo})
                flash("✅ Bloqueo automático removido", "success")
            else:
                flash("⚠️ El usuario no tiene bloqueos activos", "warning")
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al desbloquear: {e}", "danger")
    
    return redirect(url_for("usuarios_sistema"))

@app.route("/usuario/cambiar-clave/<int:usuario_id>", methods=["POST"])
@login_required
@admin_required
def cambiar_clave_usuario(usuario_id):
    """El administrador reestablece la contraseña de otro usuario del sistema."""
    usuario = db.session.get(UsuarioSistema, usuario_id)
    if not usuario:
        flash("❌ Usuario no encontrado", "danger")
        return redirect(url_for("usuarios_sistema"))

    nueva = request.form.get("nueva")
    confirmar = request.form.get("confirmar")

    if not nueva or len(nueva) < 8:
        flash("❌ La contraseña debe tener al menos 8 caracteres", "danger")
        return redirect(url_for("usuarios_sistema"))

    if nueva != confirmar:
        flash("❌ Las contraseñas no coinciden", "danger")
        return redirect(url_for("usuarios_sistema"))

    try:
        usuario.clave = bcrypt.generate_password_hash(nueva).decode("utf-8")
        usuario.debe_cambiar_clave = 1
        db.session.commit()
        registrar_auditoria(
            "CAMBIAR_CLAVE", "usuarios_sistema",
            f"El administrador cambió la contraseña del usuario {usuario.nombres} {usuario.apellidos}",
        )
        flash(f"✅ Contraseña actualizada para {usuario.nombres} {usuario.apellidos}. Deberá cambiarla en su próximo ingreso", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al cambiar la contraseña: {e}", "danger")

    return redirect(url_for("usuarios_sistema"))

@app.route("/usuario/editar/<int:usuario_id>", methods=["POST"])
@login_required
@admin_required
def editar_usuario_sistema(usuario_id):
    """El administrador edita un usuario del sistema (datos y/o contraseña)."""
    usuario = db.session.get(UsuarioSistema, usuario_id)
    if not usuario:
        flash("❌ Usuario no encontrado", "danger")
        return redirect(url_for("usuarios_sistema"))

    nombres = (request.form.get("nombres") or "").strip()
    apellidos = (request.form.get("apellidos") or "").strip()
    correo = (request.form.get("correo") or "").strip()
    rol = (request.form.get("rol") or "").strip()
    documento = (request.form.get("documento") or "").strip() or None
    nueva = request.form.get("nueva") or ""
    confirmar = request.form.get("confirmar") or ""

    if not nombres or not apellidos or not correo or not rol:
        flash("❌ Nombres, apellidos, correo y rol son obligatorios", "danger")
        return redirect(url_for("usuarios_sistema"))

    # Si se quiere cambiar la contraseña
    if nueva or confirmar:
        if len(nueva) < 8:
            flash("❌ La contraseña debe tener al menos 8 caracteres", "danger")
            return redirect(url_for("usuarios_sistema"))
        if nueva != confirmar:
            flash("❌ Las contraseñas no coinciden", "danger")
            return redirect(url_for("usuarios_sistema"))

    # Correo único (excluyendo al propio usuario)
    existe_correo = db.session.execute(text("""
        SELECT id FROM usuarios_sistema WHERE LOWER(correo) = LOWER(:c) AND id != :uid LIMIT 1
    """), {"c": correo, "uid": usuario_id}).fetchone()
    if existe_correo:
        flash("❌ El correo ya está en uso por otro usuario", "danger")
        return redirect(url_for("usuarios_sistema"))

    # Resolver rol_id
    rol_nombre = {"administrador": "admin", "vendedor": "vendedor"}.get(rol, rol.lower())
    rol_registro = db.session.execute(
        text("SELECT id FROM roles WHERE nombre = :n LIMIT 1"), {"n": rol_nombre}
    ).fetchone()
    if not rol_registro:
        flash("❌ Rol no válido", "danger")
        return redirect(url_for("usuarios_sistema"))

    try:
        usuario.nombres = nombres
        usuario.apellidos = apellidos
        usuario.correo = correo
        usuario.rol = rol
        usuario.rol_id = rol_registro[0]
        usuario.documento = documento
        if nueva:
            usuario.clave = bcrypt.generate_password_hash(nueva).decode("utf-8")
            usuario.debe_cambiar_clave = 1
        db.session.commit()
        registrar_auditoria(
            "EDITAR", "usuarios_sistema",
            f"El administrador editó al usuario {usuario.nombres} {usuario.apellidos}"
            + (" y cambió su contraseña" if nueva else ""),
        )
        flash(f"✅ Usuario actualizado: {usuario.nombres} {usuario.apellidos}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al actualizar: {e}", "danger")

    return redirect(url_for("usuarios_sistema"))

@app.route("/cambiar_clave", methods=["GET", "POST"])
@login_required
def cambiar_clave():
    if request.method == "POST":
        actual = request.form.get("actual")
        nueva = request.form["nueva"]
        confirmar = request.form["confirmar"]

        usuario = db.session.get(UsuarioSistema, session["usuario_id"])
        if not bcrypt.check_password_hash(usuario.clave, actual):
            flash("❌ Contraseña actual incorrecta", "danger")
            return render_template("cambiar_clave.html")

        if nueva != confirmar:
            flash("❌ Las contraseñas no coinciden", "danger")
            return render_template("cambiar_clave.html")

        if len(nueva) < 8:
            flash("❌ La contraseña debe tener al menos 8 caracteres", "danger")
            return render_template("cambiar_clave.html")

        usuario.clave = bcrypt.generate_password_hash(nueva).decode("utf-8")
        usuario.debe_cambiar_clave = 0
        db.session.commit()
        registrar_auditoria("CAMBIAR_CLAVE", "usuarios_sistema", f"El usuario {usuario.nombres} cambió su contraseña")
        flash("✅ Contraseña actualizada", "success")
        return redirect(url_for("productos"))

    return render_template("cambiar_clave.html")


@app.route("/perfil", methods=["GET", "POST"])
@login_required
@csrf_protect
def perfil():
    """Perfil del usuario de sistema: ve y edita sus propios datos.

    El rol y el estado NO son editables aquí: los cambia el administrador
    desde /usuarios-sistema. La contraseña se cambia en /cambiar_clave.
    """
    usuario = db.session.get(UsuarioSistema, session["usuario_id"])
    if not usuario:
        flash("❌ Tu usuario ya no existe en el sistema", "danger")
        return redirect(url_for("logout"))

    if request.method == "POST":
        nombres = (request.form.get("nombres") or "").strip()
        apellidos = (request.form.get("apellidos") or "").strip()
        correo = (request.form.get("correo") or "").strip().lower()
        documento = (request.form.get("documento") or "").strip()

        if not nombres or not apellidos:
            flash("❌ Nombres y apellidos son obligatorios", "danger")
            return render_template("perfil.html", usuario=usuario)

        if not correo or "@" not in correo:
            flash("❌ Ingresa un correo válido", "danger")
            return render_template("perfil.html", usuario=usuario)

        # El correo es la identidad de acceso y es UNIQUE en la tabla
        if correo != (usuario.correo or "").lower():
            existe = UsuarioSistema.query.filter(
                UsuarioSistema.correo == correo,
                UsuarioSistema.id != usuario.id
            ).first()
            if existe:
                flash("❌ Ese correo ya está registrado por otro usuario", "danger")
                return render_template("perfil.html", usuario=usuario)

        # Documento opcional, pero si viene debe ser DNI (8) o CE (9)
        if documento:
            if documento.isdigit():
                if len(documento) != 8:
                    flash("❌ El DNI debe tener exactamente 8 dígitos", "danger")
                    return render_template("perfil.html", usuario=usuario)
            elif len(documento) != 9:
                flash("❌ El CE debe tener 9 caracteres", "danger")
                return render_template("perfil.html", usuario=usuario)

        cambios = []
        if nombres != usuario.nombres:
            cambios.append("nombres")
        if apellidos != usuario.apellidos:
            cambios.append("apellidos")
        if correo != (usuario.correo or "").lower():
            cambios.append("correo")
        if documento != (usuario.documento or ""):
            cambios.append("documento")

        if not cambios:
            flash("ℹ️ No cambiaste ningún dato", "info")
            return redirect(url_for("perfil"))

        anterior = f"{usuario.nombres} {usuario.apellidos} <{usuario.correo}>"
        usuario.nombres = nombres
        usuario.apellidos = apellidos
        usuario.correo = correo
        usuario.documento = documento or None
        db.session.commit()

        # el navbar muestra el nombre cacheado en la sesión
        session["nombre"] = usuario.nombres

        registrar_auditoria("EDITAR_PERFIL", "usuarios_sistema",
                            f"{anterior} -> {nombres} {apellidos} <{correo}> "
                            f"(campos: {', '.join(cambios)})")
        flash("✅ Perfil actualizado", "success")
        return redirect(url_for("perfil"))

    productos = Producto.query.filter_by(estado=1).count()
    return render_template("perfil.html", usuario=usuario, productos=productos)


@app.route("/proveedores")
@login_required
def proveedores():
    proveedoreslocal = Proveedor.query.all()
    return render_template("proveedores.html", proveedores=proveedoreslocal)

@app.route("/proveedores/nuevo")
@login_required
@permiso_requerido("gestionar_proveedores")
def nuevo_proveedor():
    return render_template("proveedor_form.html")

@app.route("/proveedores/guardar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_proveedores")
def guardar_proveedor():
    nuevo = Proveedor(
        nombre=request.form["nombre"],
        email=request.form["email"],
        contacto=armar_telefono(request.form.get("prefijo"), request.form["contacto"]) or request.form["contacto"].strip(),
    )
    db.session.add(nuevo)
    db.session.commit()
    registrar_auditoria("CREAR", "proveedores", f"Se creó el proveedor: {nuevo.nombre}")
    flash("✅ Proveedor registrado", "success")
    return redirect(url_for("proveedores"))

@app.route("/proveedores/editar/<int:id>")
@login_required
@permiso_requerido("gestionar_proveedores")
def editar_proveedor(id):
    proveedor = db.session.get(Proveedor, id)
    if not proveedor:
        flash("❌ Proveedor no encontrado", "error")
        return redirect(url_for("proveedores"))
    return render_template("proveedor_form.html", proveedor=proveedor)

@app.route("/proveedores/actualizar/<int:id>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_proveedores")
def actualizar_proveedor(id):
    proveedor = db.session.get(Proveedor, id)
    if not proveedor:
        flash("❌ Proveedor no encontrado", "error")
        return redirect(url_for("proveedores"))
    proveedor.nombre = request.form["nombre"]
    proveedor.email = request.form["email"]
    proveedor.contacto = armar_telefono(request.form.get("prefijo"), request.form["contacto"]) or request.form["contacto"].strip()
    db.session.commit()
    flash("✅ Proveedor actualizado", "success")
    return redirect(url_for("proveedores"))

@app.route("/proveedores/eliminar/<int:id>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_proveedores")
@csrf_protect
def eliminar_proveedor(id):
    proveedor = db.session.get(Proveedor, id)
    if not proveedor:
        flash("❌ Proveedor no encontrado", "error")
        return redirect(url_for("proveedores"))
    db.session.delete(proveedor)
    db.session.commit()
    flash("✅ Proveedor eliminado", "success")
    return redirect(url_for("proveedores"))


# ============================================
# CATEGORIAS (CRUD)
# ============================================

@app.route("/categorias")
@login_required
def categorias():
    categoriaslocal = Categoria.query.order_by(Categoria.activo.desc(), Categoria.nombre).all()
    conteos = dict(
        db.session.query(Producto.id_categoria, func.count(Producto.id))
        .group_by(Producto.id_categoria).all()
    )
    return render_template("categorias.html", categorias_lista=categoriaslocal, conteos=conteos)


@app.route("/categorias/nueva")
@login_required
@permiso_requerido("gestionar_productos")
def nueva_categoria():
    return render_template("categoria_form.html", categoria=None)


@app.route("/categorias/guardar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_productos")
@csrf_protect
def guardar_categoria():
    nombre = (request.form.get("nombre") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()

    if not nombre:
        flash("❌ El nombre de la categoría es obligatorio", "error")
        return redirect(url_for("nueva_categoria"))
    if len(nombre) > 50:
        flash("❌ El nombre no puede superar los 50 caracteres", "error")
        return redirect(url_for("nueva_categoria"))

    duplicada = Categoria.query.filter(func.lower(Categoria.nombre) == nombre.lower()).first()
    if duplicada:
        flash("❌ Ya existe una categoría con ese nombre", "error")
        return redirect(url_for("nueva_categoria"))

    nueva = Categoria(nombre=nombre, descripcion=descripcion or None, activo=True)
    db.session.add(nueva)
    db.session.commit()
    registrar_auditoria("CREAR", "categorias", f"Se creó la categoría: {nombre}")
    flash("✅ Categoría registrada", "success")
    return redirect(url_for("categorias"))


@app.route("/categorias/editar/<int:id_categoria>")
@login_required
@permiso_requerido("gestionar_productos")
def editar_categoria(id_categoria):
    categoria = db.session.get(Categoria, id_categoria)
    if not categoria:
        flash("❌ Categoría no encontrada", "error")
        return redirect(url_for("categorias"))
    return render_template("categoria_form.html", categoria=categoria)


@app.route("/categorias/actualizar/<int:id_categoria>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_productos")
@csrf_protect
def actualizar_categoria(id_categoria):
    categoria = db.session.get(Categoria, id_categoria)
    if not categoria:
        flash("❌ Categoría no encontrada", "error")
        return redirect(url_for("categorias"))

    nombre = (request.form.get("nombre") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()
    activo_form = request.form.get("activo")

    if not nombre:
        flash("❌ El nombre de la categoría es obligatorio", "error")
        return redirect(url_for("editar_categoria", id_categoria=id_categoria))
    if len(nombre) > 50:
        flash("❌ El nombre no puede superar los 50 caracteres", "error")
        return redirect(url_for("editar_categoria", id_categoria=id_categoria))

    duplicada = Categoria.query.filter(
        func.lower(Categoria.nombre) == nombre.lower(),
        Categoria.id_categoria != id_categoria
    ).first()
    if duplicada:
        flash("❌ Ya existe otra categoría con ese nombre", "error")
        return redirect(url_for("editar_categoria", id_categoria=id_categoria))

    categoria.nombre = nombre
    categoria.descripcion = descripcion or None
    categoria.activo = True if activo_form == "1" else False
    db.session.commit()
    registrar_auditoria("EDITAR", "categorias", f"Se actualizó la categoría: {nombre}")
    flash("✅ Categoría actualizada", "success")
    return redirect(url_for("categorias"))


@app.route("/categorias/eliminar/<int:id_categoria>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_productos")
@csrf_protect
def eliminar_categoria(id_categoria):
    categoria = db.session.get(Categoria, id_categoria)
    if not categoria:
        flash("❌ Categoría no encontrada", "error")
        return redirect(url_for("categorias"))

    en_uso = Producto.query.filter_by(id_categoria=categoria.id_categoria).count()

    if en_uso:
        if categoria.activo:
            categoria.activo = False
            db.session.commit()
            registrar_auditoria("DESACTIVAR", "categorias",
                                f"Se desactivó la categoría: {categoria.nombre} ({en_uso} producto(s) asociado(s))")
            flash(f"⚠️ La categoría tiene {en_uso} producto(s): se desactivó en lugar de eliminarse", "warning")
        else:
            flash("ℹ️ La categoría ya estaba desactivada y tiene productos asociados", "info")
    else:
        nombre = categoria.nombre
        db.session.delete(categoria)
        db.session.commit()
        registrar_auditoria("ELIMINAR", "categorias", f"Se eliminó la categoría: {nombre}")
        flash("✅ Categoría eliminada", "success")

    return redirect(url_for("categorias"))


@app.route("/inventario")
@login_required
def inventario():
    """Inventario con valuación. El vendedor ve el stock pero sin costos ni totales a costo."""
    es_admin = session.get("rol") == "administrador"
    categoria_id = request.args.get("categoria", type=int)
    estado_filtro = request.args.get("estado") or ""
    busqueda = (request.args.get("q") or "").strip()

    query = Producto.query.filter(Producto.estado == 1)
    if categoria_id:
        query = query.filter(Producto.id_categoria == categoria_id)
    if busqueda:
        like = f"%{busqueda}%"
        query = query.filter(or_(Producto.nombre.like(like),
                                 Producto.codigo_barras.like(like)))

    productos_lista = query.order_by(Producto.nombre.asc()).all()

    filas = []
    for p in productos_lista:
        cantidad = p.cantidad or 0
        smin = p.stock_minimo if p.stock_minimo is not None else 5
        smax = p.stock_maximo if p.stock_maximo is not None else 100
        if cantidad == 0:
            estado_stock = "agotado"
        elif cantidad <= smin:
            estado_stock = "bajo"
        elif cantidad >= smax:
            estado_stock = "exceso"
        else:
            estado_stock = "normal"
        costo = float(p.costo or 0)
        precio = float(p.precio or 0)
        filas.append({
            "producto": p,
            "cantidad": cantidad,
            "stock_minimo": smin,
            "stock_maximo": smax,
            "estado_stock": estado_stock,
            "valor_costo": cantidad * costo,
            "valor_precio": cantidad * precio,
            "tiene_costo": p.costo is not None,
        })

    if estado_filtro in ("agotado", "bajo", "normal", "exceso"):
        filas = [f for f in filas if f["estado_stock"] == estado_filtro]

    totales = {
        "productos": len(filas),
        "unidades": sum(f["cantidad"] for f in filas),
        "valor_costo": sum(f["valor_costo"] for f in filas),
        "valor_precio": sum(f["valor_precio"] for f in filas),
        "con_costo": sum(1 for f in filas if f["tiene_costo"]),
    }

    categorias_lista = Categoria.query.filter_by(activo=True)\
        .order_by(Categoria.nombre.asc()).all()

    return render_template("inventario.html",
                          filas=filas,
                          totales=totales,
                          categorias_lista=categorias_lista,
                          es_admin=es_admin,
                          categoria_seleccionada=categoria_id,
                          estado_seleccionado=estado_filtro,
                          busqueda=busqueda)


@app.route("/stock-bajo")
@login_required
@permiso_requerido("gestionar_productos")
def stock_bajo():
    """Alertas de reposición: solo los productos agotados o por debajo del mínimo.

    Es el complemento operativo de /inventario: en vez de listar todo el
    catálogo, muestra lo que hay que comprar y cuánto costaría reponerlo.
    El costo unitario y el costo de reposición solo se muestran a admin.
    """
    es_admin = session.get("rol") == "administrador"
    categoria_id = request.args.get("categoria", type=int)
    solo_agotados = request.args.get("agotados") == "1"
    busqueda = (request.args.get("q") or "").strip()

    query = Producto.query.filter(Producto.estado == 1)
    if categoria_id:
        query = query.filter(Producto.id_categoria == categoria_id)
    if busqueda:
        like = f"%{busqueda}%"
        query = query.filter(or_(Producto.nombre.like(like),
                                 Producto.codigo_barras.like(like)))

    filas = []
    for p in query.order_by(Producto.nombre.asc()).all():
        cantidad = p.cantidad or 0
        smin = p.stock_minimo if p.stock_minimo is not None else 5
        # solo entra lo que hay que reponer
        if cantidad > smin:
            continue
        estado_stock = "agotado" if cantidad == 0 else "bajo"
        faltan = max(smin - cantidad, 0)
        costo = float(p.costo or 0)
        filas.append({
            "producto": p,
            "cantidad": cantidad,
            "stock_minimo": smin,
            "estado_stock": estado_stock,
            "faltan": faltan,
            "costo_unitario": costo,
            "costo_reposicion": faltan * costo,
            "tiene_costo": p.costo is not None,
        })

    if solo_agotados:
        filas = [f for f in filas if f["estado_stock"] == "agotado"]

    # agotados primero, luego por deficit descendente
    filas.sort(key=lambda f: (f["estado_stock"] != "agotado", -f["faltan"], f["producto"].nombre))

    totales = {
        "productos": len(filas),
        "agotados": sum(1 for f in filas if f["estado_stock"] == "agotado"),
        "bajos": sum(1 for f in filas if f["estado_stock"] == "bajo"),
        "unidades_a_reponer": sum(f["faltan"] for f in filas),
        "costo_reposicion": sum(f["costo_reposicion"] for f in filas),
        "sin_costo": sum(1 for f in filas if not f["tiene_costo"]),
    }

    categorias_lista = Categoria.query.filter_by(activo=True)\
        .order_by(Categoria.nombre.asc()).all()

    return render_template("stock_bajo.html",
                           filas=filas,
                           totales=totales,
                           categorias_lista=categorias_lista,
                           es_admin=es_admin,
                           categoria_seleccionada=categoria_id,
                           solo_agotados=solo_agotados,
                           busqueda=busqueda)


@app.route("/stock-bajo/reponer/<int:id>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_productos")
@csrf_protect
def reponer_stock(id):
    """Ajusta el stock de un producto desde la alerta de reposición."""
    producto_obj = db.session.get(Producto, id)
    if not producto_obj:
        flash("❌ Producto no encontrado", "error")
        return redirect(url_for("stock_bajo"))

    try:
        cantidad = int(request.form.get("cantidad"))
    except (TypeError, ValueError):
        flash("❌ Cantidad inválida", "error")
        return redirect(url_for("stock_bajo"))

    if cantidad < 0:
        flash("❌ La cantidad no puede ser negativa", "error")
        return redirect(url_for("stock_bajo"))

    # stock_minimo es opcional: si no viene, se deja el que ya tenía
    smin_enviado = request.form.get("stock_minimo")
    if smin_enviado not in (None, ""):
        try:
            producto_obj.stock_minimo = max(int(smin_enviado), 0)
        except (TypeError, ValueError):
            flash("❌ Stock mínimo inválido, se conservó el anterior", "error")

    anterior = producto_obj.cantidad or 0
    producto_obj.cantidad = cantidad
    db.session.commit()

    registrar_auditoria("REPOSICION", "productos",
                        f"{producto_obj.nombre}: stock {anterior} -> {cantidad}")

    flash(f"✅ Stock de «{producto_obj.nombre}» actualizado a {cantidad} unidades", "success")
    return redirect(url_for("stock_bajo"))


@app.route("/productos")
@login_required
def productos():
    categoria_id = request.args.get("categoria", type=int)
    destacado = request.args.get("destacado")
    
    query = Producto.query
    
    if categoria_id:
        query = query.filter_by(id_categoria=categoria_id)
    if destacado:
        query = query.filter_by(destacado=1)
    
    productos_lista = query.order_by(Producto.destacado.desc(), Producto.nombre.asc()).all()
    
    categorias = Categoria.query.filter_by(activo=True).all()
    
    return render_template("productos.html", 
                          productos=productos_lista,
                          categorias=categorias,
                          categoria_seleccionada=categoria_id)

@app.route("/productos/nuevo", methods=["GET"])
@login_required
@permiso_requerido("gestionar_productos")
def nuevo_producto():
    proveedores = Proveedor.query.all()
    categorias = Categoria.query.filter_by(activo=True).all()  # ← Obtener categorías activas
    return render_template("producto_form.html", 
                          proveedores=proveedores,
                          categorias=categorias)

@app.route("/productos/guardar", methods=["POST"])
@login_required
@permiso_requerido("gestionar_productos")
def guardar_producto():
    try:
        precio_oferta = request.form.get("precio_oferta")
        precio_oferta = float(precio_oferta) if precio_oferta and precio_oferta.strip() else None
        
        destacado = 1 if request.form.get("destacado") else 0
        
        id_categoria = request.form.get("id_categoria")
        id_categoria = int(id_categoria) if id_categoria and id_categoria.strip() else None
        
        costo_val = request.form.get("costo")
        costo = float(costo_val) if costo_val and costo_val.strip() else None

        nuevo = Producto(
            nombre=request.form["nombre"],
            descripcion=request.form["descripcion"],
            cantidad=int(request.form["cantidad"]),
            stock_minimo=int(request.form.get("stock_minimo") or 5),
            stock_maximo=int(request.form.get("stock_maximo") or 100),
            proveedor_id=request.form.get("proveedor") or None,
            precio=float(request.form["precio"]),
            costo=costo,
            id_categoria=id_categoria,  
            precio_oferta=precio_oferta,
            destacado=destacado,
            codigo_barras=request.form.get("codigo_barras") or None,
        )
        db.session.add(nuevo)
        db.session.flush()
        
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        if "imagen" in request.files:
            file = request.files["imagen"]
            if file and file.filename and allowed_file(file.filename):
                filename = f"{nuevo.id}_{int(time.time())}_{secure_filename(file.filename)}"
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)
                nuevo.imagen = filename
        
        db.session.commit()
        # Dual-write a microservicio inventario (dueño) - asegura dato en librospe_ms_inventario
        try:
            try:
                eng_inv = db.get_engine(bind="inventario")
            except Exception:
                eng_inv = db.engines.get("inventario") if hasattr(db, "engines") else None
            if eng_inv is not None:
                db.session.execute(text("""
                    INSERT INTO inventario_productos (id, nombre, descripcion, cantidad, proveedor_id, precio, imagen, id_categoria, precio_oferta, destacado, codigo_barras, estado, stock_minimo, stock_maximo, costo)
                    VALUES (:id, :nombre, :descripcion, :cantidad, :proveedor_id, :precio, :imagen, :id_categoria, :precio_oferta, :destacado, :codigo_barras, 1, :stock_minimo, :stock_maximo, :costo)
                    ON DUPLICATE KEY UPDATE nombre=VALUES(nombre), descripcion=VALUES(descripcion), cantidad=VALUES(cantidad), precio=VALUES(precio)
                """), {
                    "id": nuevo.id, "nombre": nuevo.nombre, "descripcion": nuevo.descripcion, "cantidad": nuevo.cantidad,
                    "proveedor_id": nuevo.proveedor_id, "precio": nuevo.precio, "imagen": nuevo.imagen, "id_categoria": nuevo.id_categoria,
                    "precio_oferta": nuevo.precio_oferta, "destacado": nuevo.destacado, "codigo_barras": nuevo.codigo_barras,
                    "stock_minimo": nuevo.stock_minimo, "stock_maximo": nuevo.stock_maximo, "costo": nuevo.costo
                }, bind_arguments={"bind": eng_inv})
                db.session.commit()
        except Exception as e:
            print(f"WARN dual-write inventario_productos: {e}")

        registrar_auditoria("CREAR", "productos", f"Se creó el producto: {nuevo.nombre}")
        flash("✅ Producto creado exitosamente", "success")
        return redirect(url_for("productos"))
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al guardar: {str(e)}", "danger")
        return redirect(url_for("nuevo_producto"))

@app.route("/productos/editar/<int:id>")
@login_required
@permiso_requerido("gestionar_productos")
def editar_producto(id):
    producto = db.session.get(Producto, id)
    if not producto:
        flash("❌ Producto no encontrado", "error")
        return redirect(url_for("productos"))
    
    proveedores = Proveedor.query.all()
    categorias = Categoria.query.filter_by(activo=True).all()  # ← Obtener categorías activas
    
    return render_template("producto_form.html", 
                          producto=producto, 
                          proveedores=proveedores,
                          categorias=categorias)

@app.route("/productos/actualizar/<int:id>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_productos")
def actualizar_producto(id):
    producto_obj = db.session.get(Producto, id)
    if not producto_obj:
        flash("❌ Producto no encontrado", "error")
        return redirect(url_for("productos"))
    
    try:
        precio_oferta = request.form.get("precio_oferta")
        precio_oferta = float(precio_oferta) if precio_oferta and precio_oferta.strip() else None
        
        id_categoria = request.form.get("id_categoria")
        id_categoria = int(id_categoria) if id_categoria and id_categoria.strip() else None
        
        producto_obj.nombre = request.form["nombre"]
        producto_obj.descripcion = request.form["descripcion"]
        producto_obj.cantidad = int(request.form["cantidad"])
        producto_obj.stock_minimo = int(request.form.get("stock_minimo") or 5)
        producto_obj.stock_maximo = int(request.form.get("stock_maximo") or 100)
        producto_obj.proveedor_id = request.form.get("proveedor") or None
        producto_obj.precio = float(request.form["precio"])
        costo_val = request.form.get("costo")
        producto_obj.costo = float(costo_val) if costo_val and costo_val.strip() else None
        producto_obj.id_categoria = id_categoria  # ← USAR id_categoria
        producto_obj.precio_oferta = precio_oferta
        producto_obj.destacado = 1 if request.form.get("destacado") else 0
        producto_obj.codigo_barras = request.form.get("codigo_barras") or None
        
        file = request.files.get("imagen")
        if file and file.filename and allowed_file(file.filename):
            if producto_obj.imagen:
                old_path = os.path.join(app.config["UPLOAD_FOLDER"], producto_obj.imagen)
                if os.path.exists(old_path):
                    os.remove(old_path)
            filename = f"{id}_{int(time.time())}_{secure_filename(file.filename)}"
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            producto_obj.imagen = filename
        
        db.session.commit()
        registrar_auditoria("EDITAR", "productos", f"Se actualizó el producto: {producto_obj.nombre}")
        verificar_stock_bajo_y_notificar()
        flash("✅ Producto actualizado exitosamente", "success")
        return redirect(url_for("productos"))
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al actualizar: {str(e)}", "danger")
        return redirect(url_for("editar_producto", id=id))

@app.route("/productos/eliminar/<int:id>", methods=["POST"])
@login_required
@permiso_requerido("gestionar_productos")
@csrf_protect
def eliminar_producto(id):
    producto_obj = db.session.get(Producto, id)
    if not producto_obj:
        flash("❌ Producto no encontrado", "error")
        return redirect(url_for("productos"))
    
    try:
        if producto_obj.imagen:
            carpeta_subidas = Path(app.config["UPLOAD_FOLDER"]).resolve()
            img_path = (carpeta_subidas / producto_obj.imagen).resolve()
            if carpeta_subidas in img_path.parents and img_path.is_file():
                img_path.unlink()
        
        db.session.delete(producto_obj)
        db.session.commit()
        registrar_auditoria("ELIMINAR", "productos", f"Se eliminó el producto: {producto_obj.nombre}")
        flash("✅ Producto eliminado exitosamente", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al eliminar: {str(e)}", "danger")
    
    return redirect(url_for("productos"))

@app.route("/producto/preview/<int:producto_id>")
@login_required
def producto_preview(producto_id):
    producto = db.session.get(Producto, producto_id)
    if not producto:
        return {"error": "Producto no encontrado"}, 404
    
    imagen_url = None
    if producto.imagen:
        imagen_url = url_for("static", filename=f"img/productos/{producto.imagen}")
    
    return {
        "id": producto.id,
        "nombre": producto.nombre,
        "descripcion": producto.descripcion[:60] + "..." if len(producto.descripcion or "") > 60 else (producto.descripcion or ""),
        "precio": float(producto.precio or 0),
        "cantidad": producto.cantidad,
        "categoria": producto.categoria_rel.nombre if producto.categoria_rel else None,  # ← AGREGAR
        "imagen_url": imagen_url,
    }



@app.route("/ventas/nueva", methods=["GET", "POST"])
@login_required
def venta_nueva():
    lista_productos = Producto.query.filter(Producto.cantidad > 0).order_by(Producto.nombre).all()
    
    if session.get("rol") == "administrador":
        vendedores = UsuarioSistema.query.filter(UsuarioSistema.rol.in_(['administrador', 'vendedor'])).order_by(UsuarioSistema.nombres).all()
    else:
        vendedor = UsuarioSistema.query.filter_by(id=session.get("usuario_id")).first()
        vendedores = [vendedor] if vendedor else []
    
    if request.method == "POST":
        try:
            # Control anti-doble clic: evitar ventas duplicadas
            ultima_venta = session.get("ultima_venta_ts")
            if ultima_venta and (time.time() - ultima_venta) < 2:
                flash("⚠️ Estás registrando ventas muy rápido. Espera un momento.", "warning")
                return render_template("ventas_form.html", productos=lista_productos, vendedores=vendedores, now=datetime.now())
            session["ultima_venta_ts"] = time.time()

            producto_id = int(request.form["producto_id"])
            cantidad = int(request.form["cantidad"])
            fecha_venta = datetime.now()
            tipo_comprobante = request.form.get("tipo_comprobante", "boleta")
            
            if session.get("rol") == "administrador":
                vendedor_id = int(request.form.get("vendedor_id", session.get("usuario_id")))
            else:
                vendedor_id = session.get("usuario_id")
            
            # ============================================
            # RECOLECTAR DATOS DEL CLIENTE
            # ============================================
            cliente_email = request.form.get("cliente_email", "")
            cliente_nombres = request.form.get("cliente_nombres", "")
            cliente_apellidos = request.form.get("cliente_apellidos", "")
            cliente_documento = request.form.get("cliente_documento", "")
            tipo_documento_cliente = request.form.get("tipo_documento_cliente", "")
            enviar_email = request.form.get("enviar_email", "0")
            
            # Si el documento está registrado, completar el correo/nombre faltante automáticamente;
            # si no hay documento, buscar el cliente por nombre/apellido exacto para jalar su DNI y correo.
            cliente_existente = None
            try:
                if cliente_documento:
                    cliente_existente = Cliente.query.filter(
                        or_(Cliente.dni == cliente_documento, Cliente.ruc == cliente_documento, Cliente.ce == cliente_documento)
                    ).first()
                elif (cliente_nombres or "").strip():
                    busqueda = Cliente.query.filter(
                        func.lower(Cliente.nombres) == cliente_nombres.strip().lower()
                    )
                    if (cliente_apellidos or "").strip():
                        busqueda = busqueda.filter(
                            func.lower(Cliente.apellidos) == cliente_apellidos.strip().lower()
                        )
                    cliente_existente = busqueda.first()
                if cliente_existente:
                    if not cliente_email and cliente_existente.correo:
                        cliente_email = cliente_existente.correo.strip()
                    if not cliente_nombres:
                        cliente_nombres = cliente_existente.nombres or ""
                    if not cliente_apellidos:
                        cliente_apellidos = cliente_existente.apellidos or ""
                    if not cliente_documento:
                        cliente_documento = cliente_existente.dni or cliente_existente.ruc or ""
            except Exception as e:
                print(f"⚠️ No se pudo buscar cliente: {e}")
            
            print(f"\n📋 VENTA: Producto ID={producto_id}, Cantidad={cantidad}, Email={cliente_email}")
            
            # Generar número de comprobante
            numero_comprobante = f"{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
            
            producto = Producto.query.get(producto_id)
            if not producto:
                flash("❌ Producto no encontrado", "danger")
                return render_template("ventas_form.html", productos=lista_productos, vendedores=vendedores, now=datetime.now())
            
            if producto.cantidad < cantidad:
                flash(f"❌ Stock insuficiente. Disponible: {producto.cantidad}", "danger")
                return render_template("ventas_form.html", productos=lista_productos, vendedores=vendedores, now=datetime.now())
            
            precio_unitario = float(producto.precio or 0)
            total_venta = precio_unitario * cantidad
            
            # ============================================
            # MÉTODO DE PAGO Y VUELTO (tienda presencial)
            # ============================================
            metodo_pago = request.form.get("metodo_pago", "efectivo")
            monto_recibido = None
            vuelto = None
            if metodo_pago == "efectivo":
                try:
                    monto_recibido = float(request.form.get("monto_recibido", "0") or 0)
                    vuelto = round(monto_recibido - total_venta, 2)
                    if vuelto < 0:
                        vuelto = 0
                except (TypeError, ValueError):
                    monto_recibido = None
                    vuelto = None
            
            # ============================================
            # CREAR VENTA - SOLO COLUMNAS QUE EXISTEN
            # ============================================
            nueva_venta = Venta(
                producto_id=producto_id,
                cantidad=cantidad,
                fecha_venta=fecha_venta,
                vendedor_id=vendedor_id,
                tipo_comprobante=tipo_comprobante,
                numero_comprobante=numero_comprobante,
                metodo_pago=metodo_pago,
                monto_recibido=monto_recibido,
                vuelto=vuelto,
                cliente_nombres=cliente_nombres or None,
                cliente_apellidos=cliente_apellidos or None,
                cliente_documento=cliente_documento or None,
                cliente_tipo_documento=(tipo_documento_cliente or ("RUC" if tipo_comprobante == "factura" else None)),
                cliente_email=cliente_email or None,
                cliente_id=cliente_existente.id if cliente_existente else None,
            )
            db.session.add(nueva_venta)
            producto.cantidad -= cantidad
            db.session.commit()
            registrar_auditoria("VENTA", "ventas", f"Venta #{nueva_venta.id} - {producto.nombre} x{cantidad} - Total: S/ {total_venta:.2f} ({metodo_pago})")
            verificar_stock_bajo_y_notificar()
            
            print(f"✅ Venta #{nueva_venta.id} registrada - Total: S/. {total_venta:.2f}")
            
            # ============================================
            # ENVIAR CORREO (si se solicitó)
            # ============================================
            if enviar_email == "1" and cliente_email and '@' in cliente_email:
                try:
                    enviar_comprobante_email(
                        destinatario=cliente_email,
                        cliente_nombre=cliente_nombres if cliente_nombres else "Cliente",
                        tipo_comprobante=tipo_comprobante,
                        numero_comprobante=numero_comprobante,
                        fecha=fecha_venta,
                        productos=[{'nombre': producto.nombre, 'cantidad': cantidad, 'precio_unitario': precio_unitario, 'total': total_venta}],
                        total_venta=total_venta,
                        documento=cliente_documento,
                        tipo_documento="RUC" if tipo_comprobante == "factura" else (tipo_documento_cliente or ("DNI" if cliente_documento else "")),
                        razon_social=request.form.get("cliente_razon_social", ""),
                        direccion_fiscal=request.form.get("factura_direccion", ""),
                    )
                    flash(f"✅ {tipo_comprobante.upper()} registrada y enviada a {cliente_email}", "success")
                except Exception as e:
                    print(f"❌ Error enviando email: {e}")
                    flash(f"⚠️ Venta registrada, pero error al enviar correo", "warning")
            else:
                flash(f"✅ Venta #{nueva_venta.id} registrada - Total: S/. {total_venta:.2f}", "success")
            
            return redirect(url_for("ver_comprobante", venta_id=nueva_venta.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            flash(f"❌ Error al registrar la venta: {str(e)}", "danger")
            return render_template("ventas_form.html", productos=lista_productos, vendedores=vendedores, now=datetime.now())
    
    return render_template("ventas_form.html", productos=lista_productos, vendedores=vendedores, now=datetime.now())

# ===============================
# CAJA - APERTURA Y CIERRE
# ===============================
@app.route("/caja")
@login_required
@permiso_requerido("ver_caja")
def ver_caja():
    caja_abierta = Caja.query.filter_by(estado="abierta").order_by(Caja.id.desc()).first()
    historial = Caja.query.filter_by(estado="cerrada").order_by(Caja.id.desc()).limit(10).all()

    # Resumen de ventas de la caja abierta (por método de pago)
    resumen = {}
    total_caja = 0
    if caja_abierta:
        ventas = Venta.query.filter(
            Venta.fecha_venta >= caja_abierta.fecha_apertura,
            Venta.estado == 1
        ).all()
        for v in ventas:
            if not v.producto:
                continue
            subtotal = float(v.cantidad) * float(v.producto.precio or 0)
            total_caja += subtotal
            metodo = v.metodo_pago or "efectivo"
            resumen[metodo] = resumen.get(metodo, 0) + subtotal
        caja_abierta._total_ventas = total_caja
        caja_abierta._resumen = resumen

    total_esperado = round(float(caja_abierta.monto_inicial or 0) + total_caja, 2) if caja_abierta else 0
    return render_template("caja.html", caja=caja_abierta, historial=historial, total_caja=total_caja, resumen=resumen, total_esperado=total_esperado)

@app.route("/caja/apertura", methods=["POST"])
@login_required
@permiso_requerido("ver_caja")
def abrir_caja():
    if Caja.query.filter_by(estado="abierta").first():
        flash("⚠️ Ya hay una caja abierta", "warning")
        return redirect(url_for("ver_caja"))
    try:
        monto_inicial = float(request.form.get("monto_inicial", "0") or 0)
    except ValueError:
        monto_inicial = 0
    caja = Caja(usuario_id=session["usuario_id"], monto_inicial=monto_inicial, estado="abierta")
    db.session.add(caja)
    db.session.commit()
    flash("✅ Caja abierta correctamente", "success")
    return redirect(url_for("ver_caja"))

@app.route("/caja/cierre", methods=["POST"])
@login_required
@permiso_requerido("ver_caja")
def cerrar_caja():
    caja = Caja.query.filter_by(estado="abierta").first()
    if not caja:
        flash("❌ No hay caja abierta", "danger")
        return redirect(url_for("ver_caja"))

    ventas = Venta.query.filter(
        Venta.fecha_venta >= caja.fecha_apertura,
        Venta.estado == 1
    ).all()
    total_ventas = 0
    for v in ventas:
        if v.producto:
            total_ventas += float(v.cantidad) * float(v.producto.precio or 0)

    monto_esperado = round(float(caja.monto_inicial or 0) + total_ventas, 2)
    try:
        monto_real = float(request.form.get("monto_real", "0") or 0)
    except ValueError:
        monto_real = 0
    diferencia = round(monto_real - monto_esperado, 2)

    caja.fecha_cierre = datetime.now()
    caja.monto_esperado = monto_esperado
    caja.monto_real = monto_real
    caja.diferencia = diferencia
    caja.estado = "cerrada"
    db.session.commit()
    flash(f"✅ Caja cerrada. Esperado: S/. {monto_esperado:.2f} | Real: S/. {monto_real:.2f} | Diferencia: S/. {diferencia:.2f}", "success")
    return redirect(url_for("ver_caja"))

# ===============================
# EXPORTAR REPORTES A PDF
# ===============================
def _generar_pdf(titulo, encabezados, filas, subtitulo=""):
    """Genera un PDF con reportlab y devuelve el buffer."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=20)
    estilos = getSampleStyleSheet()
    elementos = []
    elementos.append(Paragraph(titulo, estilos['Title']))
    if subtitulo:
        elementos.append(Paragraph(subtitulo, estilos['Italic']))
    elementos.append(Spacer(1, 14))

    data = [encabezados] + filas
    tabla = Table(data, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))
    elementos.append(tabla)
    doc.build(elementos)
    buffer.seek(0)
    return buffer

@app.route("/reportes/ventas/pdf")
@login_required
@permiso_requerido("ver_reportes")
def reporte_ventas_pdf():
    """Exporta el reporte de ventas a PDF (vendedor ve solo las suyas)."""
    if session.get("rol") == "vendedor":
        vendedor_filtro = session.get("usuario_id")
    else:
        vendedor_filtro = request.args.get('vendedor_id', type=int)

    query = """
        SELECT v.id, v.fecha_venta, p.nombre AS producto, v.cantidad,
               p.precio, (v.cantidad * p.precio) AS total,
               v.metodo_pago, u.nombres AS vendedor
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        LEFT JOIN usuarios_sistema u ON v.vendedor_id = u.id
        WHERE v.estado = 1
    """
    params = {}
    if vendedor_filtro:
        query += " AND v.vendedor_id = :vid"
        params['vid'] = vendedor_filtro
    periodo = request.args.get("periodo", "todo")
    fecha_desde = request.args.get("fecha_desde", "")
    fecha_hasta = request.args.get("fecha_hasta", "")
    inicio, fin = rango_periodo(periodo)
    if inicio and fin:
        query += " AND DATE(v.fecha_venta) >= :fini AND DATE(v.fecha_venta) <= :ffin"
        params['fini'] = inicio
        params['ffin'] = fin
    elif fecha_desde:
        query += " AND DATE(v.fecha_venta) >= :fdesde"
        params['fdesde'] = fecha_desde
    if fecha_hasta:
        query += " AND DATE(v.fecha_venta) <= :fhasta"
        params['fhasta'] = fecha_hasta
    query += " ORDER BY v.fecha_venta DESC"

    rows = db.session.execute(db.text(query), params).mappings().all()

    encabezados = ["N°", "Fecha", "Producto", "Cant.", "P. Unit.", "Total", "Método", "Vendedor"]
    filas = []
    total_gral = 0
    for i, r in enumerate(rows, 1):
        total = float(r['total'] or 0)
        total_gral += total
        filas.append([
            i,
            r['fecha_venta'].strftime('%d/%m/%Y %H:%M') if r['fecha_venta'] else '',
            r['producto'],
            r['cantidad'],
            f"S/ {float(r['precio'] or 0):.2f}",
            f"S/ {total:.2f}",
            (r['metodo_pago'] or 'efectivo').capitalize(),
            r['vendedor'] or '-',
        ])
    filas.append(["", "", "", "", "TOTAL", f"S/ {total_gral:.2f}", "", ""])

    subtitulo = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if inicio and fin:
        etiquetas = {"hoy": "Hoy", "semana": "Esta semana", "mes": "Este mes", "anio": "Este año"}
        subtitulo += f" | Período: {etiquetas.get(periodo, periodo)} ({inicio.strftime('%d/%m/%Y')} - {fin.strftime('%d/%m/%Y')})"
    elif fecha_desde or fecha_hasta:
        subtitulo += f" | Desde: {fecha_desde or '-'} Hasta: {fecha_hasta or '-'}"
    buffer = _generar_pdf("Reporte de Ventas - Librería Salesiana", encabezados, filas, subtitulo)
    return send_file(buffer, as_attachment=True, download_name="reporte_ventas.pdf", mimetype="application/pdf")

@app.route("/reportes/ventas/excel")
@login_required
@permiso_requerido("ver_reportes")
def reporte_ventas_excel():
    """Exporta el reporte de ventas a Excel (vendedor ve solo las suyas)."""
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    if session.get("rol") == "vendedor":
        vendedor_filtro = session.get("usuario_id")
    else:
        vendedor_filtro = request.args.get('vendedor_id', type=int)

    query = """
        SELECT v.id, v.fecha_venta, p.nombre AS producto, v.cantidad,
               p.precio, (v.cantidad * p.precio) AS total,
               v.metodo_pago, u.nombres AS vendedor
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        LEFT JOIN usuarios_sistema u ON v.vendedor_id = u.id
        WHERE v.estado = 1
    """
    params = {}
    if vendedor_filtro:
        query += " AND v.vendedor_id = :vid"
        params['vid'] = vendedor_filtro
    periodo = request.args.get('periodo', 'todo')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    inicio, fin = rango_periodo(periodo)
    if inicio and fin:
        query += " AND DATE(v.fecha_venta) >= :fini AND DATE(v.fecha_venta) <= :ffin"
        params['fini'] = inicio
        params['ffin'] = fin
    elif fecha_desde:
        query += " AND DATE(v.fecha_venta) >= :fdesde"
        params['fdesde'] = fecha_desde
    if fecha_hasta:
        query += " AND DATE(v.fecha_venta) <= :fhasta"
        params['fhasta'] = fecha_hasta
    query += " ORDER BY v.fecha_venta DESC"
    rows = db.session.execute(db.text(query), params).mappings().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas"
    encabezados = ["N°", "Fecha", "Producto", "Cantidad", "Precio Unit.", "Total", "Método", "Vendedor"]
    ws.append(encabezados)
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        celda.alignment = Alignment(horizontal="center")

    total_gral = 0
    for i, r in enumerate(rows, 1):
        total = float(r['total'] or 0)
        total_gral += total
        ws.append([
            i,
            r['fecha_venta'].strftime('%d/%m/%Y %H:%M') if r['fecha_venta'] else '',
            r['producto'],
            r['cantidad'],
            float(r['precio'] or 0),
            total,
            (r['metodo_pago'] or 'efectivo').capitalize(),
            r['vendedor'] or '-',
        ])
    ws.append(["", "", "", "", "TOTAL", total_gral, "", ""])
    ws.append([])
    ws.append(["Generado: " + datetime.now().strftime('%d/%m/%Y %H:%M')])
    if inicio and fin:
        etiquetas = {"hoy": "Hoy", "semana": "Esta semana", "mes": "Este mes", "anio": "Este año"}
        ws.append([f"Período: {etiquetas.get(periodo, periodo)} ({inicio.strftime('%d/%m/%Y')} - {fin.strftime('%d/%m/%Y')})"])
    elif fecha_desde or fecha_hasta:
        ws.append([f"Desde: {fecha_desde or '-'} Hasta: {fecha_hasta or '-'}"])

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="reporte_ventas.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ===============================
# REPORTE VENTAS POR CLIENTE Y UBICACIÓN
# ===============================
def _listar_departamentos_clientes():
    """Lista los departamentos registrados en clientes (para el filtro)."""
    return db.session.execute(db.text(
        "SELECT DISTINCT departamento FROM clientes "
        "WHERE departamento IS NOT NULL AND TRIM(departamento) <> '' "
        "ORDER BY departamento"
    )).scalars().all()


def _consultar_ventas_por_ubicacion(periodo="todo", departamento=None, provincia=None, distrito=None):
    """Agrupa las ventas en la jerarquía departamento -> provincia -> distrito -> cliente.

    Devuelve una tupla (filas, totales):
      filas   : lista plana con {nivel, tipo, nombre, num_ventas, unidades, total}
      totales : {num_ventas, unidades, total} del filtro aplicado.
    Los vendedores solo ven sus propias ventas.
    """
    query = """
        SELECT COALESCE(c.departamento, 'SIN ESPECIFICAR') AS departamento,
               COALESCE(c.provincia, 'Sin especificar')    AS provincia,
               COALESCE(c.distrito, 'Sin especificar')     AS distrito,
               COALESCE(CONCAT(c.nombres, ' ', c.apellidos), 'VENTA SIN CLIENTE (mostrador)') AS cliente,
               COUNT(*)                    AS num_ventas,
               COALESCE(SUM(v.cantidad), 0) AS unidades,
               COALESCE(SUM(v.cantidad * p.precio), 0) AS total
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        LEFT JOIN clientes c ON (v.cliente_id IS NOT NULL AND v.cliente_id = c.id)
             OR (v.cliente_id IS NULL AND v.cliente_documento IS NOT NULL
                 AND v.cliente_documento <> ''
                 AND (c.dni = v.cliente_documento OR c.ruc = v.cliente_documento OR c.ce = v.cliente_documento))
        WHERE v.estado = 1
    """
    params = {}
    if session.get("rol") == "vendedor":
        query += " AND v.vendedor_id = :vid"
        params["vid"] = session.get("usuario_id")
    inicio, fin = rango_periodo(periodo)
    if inicio and fin:
        query += " AND DATE(v.fecha_venta) >= :fini AND DATE(v.fecha_venta) <= :ffin"
        params["fini"] = inicio
        params["ffin"] = fin
    if departamento:
        query += " AND UPPER(c.departamento) = UPPER(:dep)"
        params["dep"] = departamento
    if provincia:
        query += " AND UPPER(c.provincia) = UPPER(:prov)"
        params["prov"] = provincia
    if distrito:
        query += " AND UPPER(c.distrito) = UPPER(:dist)"
        params["dist"] = distrito
    query += """
        GROUP BY c.id, c.departamento, c.provincia, c.distrito, c.nombres, c.apellidos
        ORDER BY c.departamento IS NULL, c.departamento,
                 c.provincia IS NULL, c.provincia,
                 c.distrito IS NULL, c.distrito,
                 c.nombres, c.apellidos
    """
    rows = db.session.execute(db.text(query), params).mappings().all()

    datos = []
    for r in rows:
        datos.append({
            "d": r["departamento"],
            "p": r["provincia"],
            "dt": r["distrito"],
            "cliente": r["cliente"],
            "num_ventas": int(r["num_ventas"] or 0),
            "unidades": int(r["unidades"] or 0),
            "total": float(r["total"] or 0),
        })

    arbol = {}
    for item in datos:
        arbol.setdefault(item["d"], {}).setdefault(item["p"], {}).setdefault(item["dt"], []).append(item)

    def _subtotal(lista):
        return (
            sum(x["num_ventas"] for x in lista),
            sum(x["unidades"] for x in lista),
            round(sum(x["total"] for x in lista), 2),
        )

    filas = []
    tot_ventas = tot_unidades = 0
    tot_total = 0.0
    for dep, provs in arbol.items():
        clientes_dep = [c for p in provs.values() for ds in p.values() for c in ds]
        n, u, t = _subtotal(clientes_dep)
        filas.append({"nivel": 0, "tipo": "departamento", "nombre": dep, "num_ventas": n, "unidades": u, "total": t})
        for prov, dists in provs.items():
            clientes_prov = [c for ds in dists.values() for c in ds]
            n, u, t = _subtotal(clientes_prov)
            filas.append({"nivel": 1, "tipo": "provincia", "nombre": prov, "num_ventas": n, "unidades": u, "total": t})
            for dist, clientes in dists.items():
                n, u, t = _subtotal(clientes)
                filas.append({"nivel": 2, "tipo": "distrito", "nombre": dist, "num_ventas": n, "unidades": u, "total": t})
                for c in clientes:
                    filas.append({"nivel": 3, "tipo": "cliente", "nombre": c["cliente"], "num_ventas": c["num_ventas"], "unidades": c["unidades"], "total": c["total"]})
                    tot_ventas += c["num_ventas"]
                    tot_unidades += c["unidades"]
                    tot_total += c["total"]

    totales = {"num_ventas": tot_ventas, "unidades": tot_unidades, "total": round(tot_total, 2)}
    return filas, totales


@app.route("/reportes/ventas_por_ubicacion", methods=["GET", "POST"])
@login_required
@permiso_requerido("ver_reportes")
def reporte_ventas_por_ubicacion():
    """Página del reporte de ventas por cliente agrupado por ubicación."""
    periodo = request.args.get("periodo") or request.form.get("periodo") or "todo"
    departamento = (request.args.get("departamento") or request.form.get("departamento") or "").strip() or None
    provincia = (request.args.get("provincia") or request.form.get("provincia") or "").strip() or None
    distrito = (request.args.get("distrito") or request.form.get("distrito") or "").strip() or None
    filas, totales = _consultar_ventas_por_ubicacion(periodo, departamento, provincia, distrito)
    deptos = _listar_departamentos_clientes()
    return render_template(
        "reporte_ventas_ubicacion.html",
        filas=filas,
        totales=totales,
        periodo=periodo,
        departamento=departamento,
        provincia=provincia,
        distrito=distrito,
        deptos=deptos,
    )


@app.route("/reportes/ventas_por_ubicacion/fragmento", methods=["POST"])
@login_required
@permiso_requerido("ver_reportes")
def reporte_ventas_por_ubicacion_fragmento():
    """Devuelve solo la tabla del reporte (AJAX, sin recargar la página)."""
    periodo = request.form.get("periodo") or "todo"
    departamento = (request.form.get("departamento") or "").strip() or None
    provincia = (request.form.get("provincia") or "").strip() or None
    distrito = (request.form.get("distrito") or "").strip() or None
    filas, totales = _consultar_ventas_por_ubicacion(periodo, departamento, provincia, distrito)
    return render_template("partials/_ubicacion_tabla.html", filas=filas, totales=totales)


@app.route("/reportes/ventas_por_ubicacion/pdf")
@login_required
@permiso_requerido("ver_reportes")
def reporte_ventas_por_ubicacion_pdf():
    """Exporta el reporte de ventas por ubicación a PDF."""
    periodo = request.args.get("periodo") or "todo"
    departamento = (request.args.get("departamento") or "").strip() or None
    provincia = (request.args.get("provincia") or "").strip() or None
    distrito = (request.args.get("distrito") or "").strip() or None
    filas, totales = _consultar_ventas_por_ubicacion(periodo, departamento, provincia, distrito)

    encabezados = ["Ubicación / Cliente", "N° Compras", "Unidades", "Total (S/)"]
    filas_pdf = [[("    " * f["nivel"]) + f["tipo"].capitalize() + ": " + f["nombre"],
                  f["num_ventas"], f["unidades"], f"S/ {f['total']:.2f}"] for f in filas]
    filas_pdf.append(["", "", "", ""])
    filas_pdf.append(["TOTAL GENERAL", totales["num_ventas"], totales["unidades"], f"S/ {totales['total']:.2f}"])

    subtitulo = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if periodo != "todo":
        inicio, fin = rango_periodo(periodo)
        subtitulo += f" | Período: {inicio.strftime('%d/%m/%Y')} - {fin.strftime('%d/%m/%Y')}"
    if departamento:
        subtitulo += f" | Departamento: {departamento}"
    if provincia:
        subtitulo += f" | Provincia: {provincia}"
    if distrito:
        subtitulo += f" | Distrito: {distrito}"

    buffer = _generar_pdf("Ventas por Cliente y Ubicación", encabezados, filas_pdf, subtitulo)
    return send_file(buffer, as_attachment=True, download_name="reporte_ventas_por_ubicacion.pdf", mimetype="application/pdf")


@app.route("/reportes/ventas_por_ubicacion/excel")
@login_required
@permiso_requerido("ver_reportes")
def reporte_ventas_por_ubicacion_excel():
    """Exporta el reporte de ventas por ubicación a Excel."""
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    periodo = request.args.get("periodo") or "todo"
    departamento = (request.args.get("departamento") or "").strip() or None
    provincia = (request.args.get("provincia") or "").strip() or None
    distrito = (request.args.get("distrito") or "").strip() or None
    filas, totales = _consultar_ventas_por_ubicacion(periodo, departamento, provincia, distrito)

    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas por Ubicación"
    ws.append(["UBICACIÓN / CLIENTE", "N° COMPRAS", "UNIDADES", "TOTAL (S/)"])
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        celda.alignment = Alignment(horizontal="center")

    for f in filas:
        ws.append([("    " * f["nivel"]) + f["tipo"].capitalize() + ": " + f["nombre"],
                   f["num_ventas"], f["unidades"], round(f["total"], 2)])
    ws.append([])
    ws.append(["TOTAL GENERAL", totales["num_ventas"], totales["unidades"], round(totales["total"], 2)])

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="reporte_ventas_por_ubicacion.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/caja/cierre/pdf")
@login_required
@permiso_requerido("ver_caja")
def caja_cierre_pdf():
    """Exporta el cierre de caja a PDF (solo administrador)."""
    caja_id = request.args.get('caja_id', type=int)
    caja = db.session.get(Caja, caja_id) if caja_id else Caja.query.filter_by(estado="cerrada").order_by(Caja.id.desc()).first()
    if not caja:
        flash("❌ Caja no encontrada", "danger")
        return redirect(url_for("ver_caja"))

    ventas = Venta.query.filter(Venta.fecha_venta >= caja.fecha_apertura, Venta.estado == 1).all()
    total_ventas = 0
    resumen = {}
    for v in ventas:
        if not v.producto:
            continue
        subtotal = float(v.cantidad) * float(v.producto.precio or 0)
        total_ventas += subtotal
        metodo = v.metodo_pago or "efectivo"
        resumen[metodo] = resumen.get(metodo, 0) + subtotal

    encabezados = ["Método de pago", "Monto"]
    filas = [[m.capitalize(), f"S/ {monto:.2f}"] for m, monto in resumen.items()]
    filas.append(["TOTAL VENTAS", f"S/ {total_ventas:.2f}"])
    filas.append(["Monto inicial", f"S/ {float(caja.monto_inicial or 0):.2f}"])
    filas.append(["Monto esperado", f"S/ {float(caja.monto_esperado or 0):.2f}"])
    filas.append(["Monto real contado", f"S/ {float(caja.monto_real or 0):.2f}"])
    filas.append(["DIFERENCIA", f"S/ {float(caja.diferencia or 0):.2f}"])

    buffer = _generar_pdf("Cierre de Caja - Librería Salesiana", encabezados, filas,
                          f"Caja N° {caja.id} | Apertura: {caja.fecha_apertura.strftime('%d/%m/%Y %H:%M')} | Cierre: {(caja.fecha_cierre or datetime.now()).strftime('%d/%m/%Y %H:%M')}")
    return send_file(buffer, as_attachment=True, download_name=f"cierre_caja_{caja.id}.pdf", mimetype="application/pdf")

# ===============================
# AUDITORÍA
# ===============================
@app.route("/auditoria")
@login_required
@permiso_requerido("ver_auditoria")
def ver_auditoria():
    registros = db.session.query(Auditoria, UsuarioSistema.nombres.label("usuario_nombre"), UsuarioSistema.apellidos.label("usuario_apellido"))\
        .outerjoin(UsuarioSistema, Auditoria.usuario_id == UsuarioSistema.id)\
        .order_by(Auditoria.id.desc()).limit(200).all()
    return render_template("auditoria.html", registros=registros)

# ===============================
# BLOQUEOS - VER Y DESBLOQUEAR
# ===============================
@app.route("/bloqueos")
@login_required
def ver_bloqueos():
    if session.get("rol") != "administrador":
        flash("❌ Solo administradores pueden ver bloqueos", "danger")
        return redirect(url_for("dashboard"))
    
    try:
        # ============================================
        # 1. BLOQUEOS PERMANENTES DE CLIENTES
        # ============================================
        bloqueos_permanentes = db.session.execute(text("""
            SELECT 
                b.id,
                b.cliente_id,
                b.motivo,
                b.fecha_bloqueo,
                b.bloqueado_por,
                b.estado,
                b.permanente,
                c.correo AS cliente_correo,
                c.nombres AS cliente_nombres,
                c.apellidos AS cliente_apellidos,
                CONCAT(bloq.nombres, ' ', bloq.apellidos) AS bloqueado_por_nombre
            FROM bloqueos b
            LEFT JOIN clientes c ON b.cliente_id = c.id
            LEFT JOIN usuarios_sistema bloq ON b.bloqueado_por = bloq.id
            WHERE b.tipo_usuario = 'cliente' AND b.estado = 1 AND b.permanente = 1
            ORDER BY b.fecha_bloqueo DESC
        """)).mappings().all()
        
        # ============================================
        # 2. BLOQUEOS TEMPORALES DE CLIENTES
        # ============================================
        bloqueos_temporales = db.session.execute(text("""
            SELECT 
                b.id,
                b.cliente_id,
                b.motivo,
                b.fecha_bloqueo,
                b.bloqueado_por,
                b.estado,
                b.permanente,
                b.minutos_bloqueo,
                c.correo AS cliente_correo,
                c.nombres AS cliente_nombres,
                c.apellidos AS cliente_apellidos,
                CONCAT(bloq.nombres, ' ', bloq.apellidos) AS bloqueado_por_nombre,
                DATE_ADD(b.fecha_bloqueo, INTERVAL b.minutos_bloqueo MINUTE) AS fecha_desbloqueo
            FROM bloqueos b
            LEFT JOIN clientes c ON b.cliente_id = c.id
            LEFT JOIN usuarios_sistema bloq ON b.bloqueado_por = bloq.id
            WHERE b.tipo_usuario = 'cliente' AND b.estado = 1 AND b.permanente = 0
            ORDER BY b.fecha_bloqueo DESC
        """)).mappings().all()
        
        # ============================================
        # 3. UNIFICAR RESULTADOS
        # ============================================
        bloqueos_lista = []
        
        # Permanentes
        for b in bloqueos_permanentes:
            bloqueo_dict = {
                'id_bloqueo': b['id'],
                'tipo': 'Cliente',
                'nombre_completo': f"{b['cliente_nombres'] or ''} {b['cliente_apellidos'] or ''}".strip(),
                'email': b['cliente_correo'],
                'motivo': b['motivo'] or 'Sin motivo',
                'fecha_bloqueo': b['fecha_bloqueo'],
                'bloqueado_por': b['bloqueado_por_nombre'] or 'Sistema',
                'origen': 'Permanente',
                'tipo_origen': 'bloqueos',
                'permanente': True
            }
            bloqueos_lista.append(bloqueo_dict)
        
        # Temporales
        for b in bloqueos_temporales:
            bloqueo_dict = {
                'id_bloqueo': b['id'],
                'tipo': 'Cliente',
                'nombre_completo': f"{b['cliente_nombres'] or ''} {b['cliente_apellidos'] or ''}".strip(),
                'email': b['cliente_correo'],
                'motivo': b['motivo'] or 'Sin motivo',
                'fecha_bloqueo': b['fecha_bloqueo'],
                'bloqueado_por': b['bloqueado_por_nombre'] or 'Sistema',
                'origen': 'Temporal (10 min)',
                'tipo_origen': 'bloqueos',
                'permanente': False,
                'fecha_desbloqueo': b['fecha_desbloqueo']
            }
            bloqueos_lista.append(bloqueo_dict)
        
        return render_template("bloqueos.html", bloqueos=bloqueos_lista)
        
    except Exception as e:
        print(f"❌ Error en bloqueos: {e}")
        flash(f"Error al cargar bloqueos: {e}", "danger")
        return render_template("bloqueos.html", bloqueos=[])

@app.route("/ips-bloqueadas")
@login_required
@admin_required
def ver_ips_bloqueadas():
    """Lista las direcciones IP que mantienen un bloqueo temporal activo."""
    ahora = datetime.now()
    ips = IntentosLogin.query.filter(
        IntentosLogin.ips_bloqueadas.isnot(None),
        IntentosLogin.ips_bloqueadas > ahora,
    ).order_by(IntentosLogin.ips_bloqueadas.desc()).all()
    return render_template("ips_bloqueadas.html", ips=ips)

@app.route("/ips-bloqueadas/<path:ip>/desbloquear", methods=["POST"])
@login_required
@admin_required
@csrf_protect
def desbloquear_ip(ip):
    """Elimina el bloqueo temporal de una IP desde el panel de administración."""
    IntentosLogin.query.filter_by(ip=ip).update(
        {IntentosLogin.ips_bloqueadas: None, IntentosLogin.intentos: 0},
        synchronize_session=False,
    )
    db.session.commit()
    flash("IP desbloqueada correctamente", "success")
    return redirect(url_for("ver_ips_bloqueadas"))

@app.route("/desbloquear-intento-login", methods=["POST"])
@login_required
def desbloquear_intento_login():
    """Desbloquear un email de la tabla intentos_login"""
    if session.get("rol") != "administrador":
        flash("❌ No autorizado", "danger")
        return redirect(url_for("ver_bloqueos"))
    
    email = request.form.get("email")
    
    if not email:
        flash("❌ Email no proporcionado", "danger")
        return redirect(url_for("ver_bloqueos"))
    
    try:
        db.session.execute(text("""
            UPDATE intentos_login 
            SET email_bloqueado = NULL, intentos = 0 
            WHERE email = :email
        """), {"email": email})
        
        db.session.commit()
        flash(f"✅ Usuario {email} desbloqueado exitosamente", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al desbloquear: {e}", "danger")
    
    return redirect(url_for("ver_bloqueos"))

@app.route("/bloqueos/desbloquear/<int:bloqueo_id>", methods=["POST"])
@login_required
def desbloquear_usuario_admin(bloqueo_id):
    """Desbloquear un usuario o cliente desde el panel de administración"""
    if session.get("rol") != "administrador":
        return jsonify({"success": False, "error": "No autorizado"}), 403
    
    try:
        # Obtener el bloqueo
        bloqueo = db.session.execute(text("""
            SELECT * FROM bloqueos WHERE id = :id AND estado = 1
        """), {"id": bloqueo_id}).mappings().first()
        
        if not bloqueo:
            return jsonify({"success": False, "error": "Bloqueo no encontrado"}), 404
        
        # Desbloquear usando el procedimiento
        db.session.execute(text("""
            CALL desbloquear_usuario(:bloqueo_id, :admin_id)
        """), {"bloqueo_id": bloqueo_id, "admin_id": session["usuario_id"]})
        
        db.session.commit()
        
        return jsonify({"success": True, "message": "Usuario desbloqueado exitosamente"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/bloqueos/desbloquear", methods=["POST"])
@login_required
def desbloquear_usuario_form():
    """Desbloquear usuario desde formulario"""
    if session.get("rol") != "administrador":
        flash("❌ No autorizado", "danger")
        return redirect(url_for("ver_bloqueos"))
    
    bloqueo_id = request.form.get("bloqueo_id")
    
    if not bloqueo_id:
        flash("❌ ID de bloqueo no proporcionado", "danger")
        return redirect(url_for("ver_bloqueos"))
    
    try:
        db.session.execute(text("""
            CALL desbloquear_usuario(:bloqueo_id, :admin_id)
        """), {"bloqueo_id": bloqueo_id, "admin_id": session["usuario_id"]})
        
        db.session.commit()
        flash("✅ Usuario desbloqueado exitosamente", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al desbloquear: {str(e)}", "danger")
    
    return redirect(url_for("ver_bloqueos"))


@app.route("/api/bloqueos")
@login_required
def api_bloqueos():
    """API para obtener bloqueos activos de CLIENTES (para el contador)"""
    try:
        # 🔥 PRIMERO: Limpiar bloqueos expirados
        limpiar_bloqueos_expirados()
        
        # ============================================
        # 1. BLOQUEOS DE LA TABLA 'bloqueos' (manuales y temporales)
        # ============================================
        bloqueos_bd = db.session.execute(text("""
            SELECT 
                b.id,
                b.cliente_id,
                b.motivo,
                b.fecha_bloqueo,
                b.permanente,
                b.minutos_bloqueo,
                c.correo AS cliente_correo,
                c.nombres AS cliente_nombres,
                c.apellidos AS cliente_apellidos
            FROM bloqueos b
            LEFT JOIN clientes c ON b.cliente_id = c.id
            WHERE b.tipo_usuario = 'cliente' 
            AND b.estado = 1
            AND (
                b.permanente = 1 
                OR b.fecha_bloqueo > DATE_SUB(NOW(), INTERVAL b.minutos_bloqueo MINUTE)
            )
            ORDER BY b.fecha_bloqueo DESC
        """)).mappings().all()
        
        # ============================================
        # 2. BLOQUEOS AUTOMÁTICOS (intentos_login)
        # ============================================
        intentos_bloqueados = db.session.execute(text("""
            SELECT 
                i.id,
                i.email,
                i.intentos,
                i.email_bloqueado,
                c.id AS cliente_id,
                c.nombres AS cliente_nombres,
                c.apellidos AS cliente_apellidos,
                c.correo AS cliente_correo
            FROM intentos_login i
            JOIN clientes c ON i.email = c.correo
            WHERE i.email_bloqueado IS NOT NULL 
            AND i.email_bloqueado > NOW()
            ORDER BY i.email_bloqueado DESC
        """)).mappings().all()
        
        # ============================================
        # 3. UNIFICAR RESULTADOS SIN DUPLICADOS
        # ============================================
        resultado = []
        emails_vistos = set()
        
        # Procesar bloqueos de la tabla 'bloqueos'
        for b in bloqueos_bd:
            email = b['cliente_correo']
            # Si ya vimos este email en intentos_login, usar el de intentos_login (más reciente)
            if email in emails_vistos:
                continue
            
            emails_vistos.add(email)
            
            resultado.append({
                'id': b['id'],
                'tipo': 'Cliente',
                'nombre_completo': f"{b['cliente_nombres'] or ''} {b['cliente_apellidos'] or ''}".strip(),
                'email': email,
                'motivo': b['motivo'] or 'Sin motivo',
                'fecha_bloqueo': b['fecha_bloqueo'],
                'origen': 'Permanente' if b['permanente'] else 'Temporal',
                'permanente': bool(b['permanente'])
            })
        
        # Procesar bloqueos automáticos de intentos_login
        for i in intentos_bloqueados:
            email = i['email']
            # Si ya vimos este email, saltar (el de intentos_login es más reciente)
            if email in emails_vistos:
                continue
            
            emails_vistos.add(email)
            
            resultado.append({
                'id': i['id'],
                'tipo': 'Cliente',
                'nombre_completo': f"{i['cliente_nombres'] or ''} {i['cliente_apellidos'] or ''}".strip(),
                'email': email,
                'motivo': f"Bloqueo automático por {i['intentos']} intentos fallidos",
                'fecha_bloqueo': i['email_bloqueado'],
                'origen': 'Automático',
                'permanente': False
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _consultar_ventas_filtradas(periodo="todo", fecha_desde="", fecha_hasta="", vendedor_filtro=None):
    """Devuelve la lista de ventas (dicts) aplicando período, rango de fechas y vendedor."""
    query = """
        SELECT 
            v.id, 
            v.cantidad, 
            v.fecha_venta, 
            v.tipo_comprobante, 
            v.numero_comprobante,
            p.nombre as producto, 
            p.precio,
            u.id as vendedor_id, 
            u.nombres as vendedor_nombres, 
            u.apellidos as vendedor_apellidos,
            v.cliente_nombres,
            v.cliente_apellidos,
            v.cliente_documento
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        LEFT JOIN usuarios_sistema u ON v.vendedor_id = u.id
        WHERE v.estado = 1
    """
    params = {}
    if vendedor_filtro:
        query += " AND v.vendedor_id = :vendedor_id"
        params['vendedor_id'] = vendedor_filtro
    inicio, fin = rango_periodo(periodo)
    if inicio and fin:
        query += " AND DATE(v.fecha_venta) >= :fini AND DATE(v.fecha_venta) <= :ffin"
        params['fini'] = inicio
        params['ffin'] = fin
    elif fecha_desde:
        query += " AND DATE(v.fecha_venta) >= :fdesde"
        params['fdesde'] = fecha_desde
    if fecha_hasta:
        query += " AND DATE(v.fecha_venta) <= :fhasta"
        params['fhasta'] = fecha_hasta
    query += " ORDER BY v.id DESC"

    resultados = db.session.execute(db.text(query), params).mappings().all()

    ventas_lista = []
    for row in resultados:
        venta_dict = dict(row)
        venta_dict['precio_unitario'] = float(venta_dict.get('precio') or 0)
        venta_dict['total_venta'] = venta_dict['precio_unitario'] * venta_dict.get('cantidad', 1)
        ventas_lista.append(venta_dict)
    return ventas_lista


@app.route("/ventas")
@login_required
def ventas():
    try:
        # Si es vendedor, solo ve sus propias ventas
        if session.get("rol") == "vendedor":
            vendedor_id = session.get("usuario_id")
            vendedor_filtro = vendedor_id
        else:
            vendedor_filtro = request.args.get('vendedor_id', type=int)
        
        # ============================================
        # PERÍODO (día, semana, mes, año, todo)
        # ============================================
        periodo = request.args.get('periodo', 'todo')
        fecha_desde = request.args.get('fecha_desde', '')
        fecha_hasta = request.args.get('fecha_hasta', '')
        
        ventas_lista = _consultar_ventas_filtradas(periodo, fecha_desde, fecha_hasta, vendedor_filtro)
        
        # Obtener lista de vendedores para el filtro (solo para administradores)
        vendedores = []
        vendedor_seleccionado = None
        vendedor_id_actual = None
        
        if session.get("rol") == "administrador":
            vendedores = UsuarioSistema.query.filter_by(rol='vendedor').all()
            vendedor_id_actual = vendedor_filtro
            if vendedor_filtro:
                vendedor_seleccionado = UsuarioSistema.query.get(vendedor_filtro)
        
        return render_template("ventas.html", 
                              ventas=ventas_lista, 
                              vendedores=vendedores,
                              vendedor_seleccionado=vendedor_seleccionado,
                              vendedor_id_actual=vendedor_id_actual,
                              rol_usuario=session.get("rol"),
                              periodo=periodo,
                              fecha_desde=fecha_desde,
                              fecha_hasta=fecha_hasta)
        
    except Exception as e:
        print(f"Error en ventas: {e}")
        flash(f"Error al cargar ventas: {str(e)}", "danger")
        return render_template("ventas.html", ventas=[], vendedores=[])

@app.route("/ventas/fragmento", methods=["POST"])
@login_required
def ventas_fragmento():
    """Devuelve la tabla de ventas filtrada como JSON (AJAX, sin recargar la página)."""
    try:
        periodo = request.form.get("periodo") or "todo"
        fecha_desde = request.form.get("fecha_desde", "")
        fecha_hasta = request.form.get("fecha_hasta", "")
        if session.get("rol") == "vendedor":
            vendedor_filtro = session.get("usuario_id")
        else:
            vendedor_filtro = request.form.get("vendedor_id", type=int)
        ventas_lista = _consultar_ventas_filtradas(periodo, fecha_desde, fecha_hasta, vendedor_filtro)
        html = render_template("partials/_ventas_tabla.html", ventas=ventas_lista, rol_usuario=session.get("rol"))
        return jsonify({"html": html, "conteo": len(ventas_lista)})
    except Exception as e:
        print(f"Error en ventas_fragmento: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/comprobante/<int:venta_id>")
@login_required
def ver_comprobante(venta_id):
    venta = db.session.query(Venta,
                              Producto.nombre.label("producto_nombre"),
                              Producto.precio,
                              UsuarioSistema.nombres.label("vendedor_nombres"),
                              UsuarioSistema.apellidos.label("vendedor_apellidos"),
                              Cliente.correo.label("cliente_email_db"),
                              Cliente.nombres.label("cliente_nombres_db"),
                              Cliente.apellidos.label("cliente_apellidos_db")
                             ).join(Producto, Venta.producto_id == Producto.id)\
                              .outerjoin(UsuarioSistema, Venta.vendedor_id == UsuarioSistema.id)\
                              .outerjoin(Cliente, or_(Venta.cliente_documento == Cliente.dni,
                                                      Venta.cliente_documento == Cliente.ruc,
                                                      Venta.cliente_documento == Cliente.ce))\
                              .filter(Venta.id == venta_id).first()
    
    if not venta:
        flash("❌ Venta no encontrada", "danger")
        return redirect(url_for("ventas"))
    
    total = venta.Venta.cantidad * venta.precio
    
    return render_template("comprobante.html", venta=venta, total=total)

@app.route("/comprobante/<int:venta_id>/pdf")
@login_required
def comprobante_pdf(venta_id):
    """Genera el PDF del comprobante (boleta/factura) con autorización SUNAT simulada."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    venta = db.session.query(Venta,
                              Producto.nombre.label("producto_nombre"),
                              Producto.precio,
                              UsuarioSistema.nombres.label("vendedor_nombres"),
                              UsuarioSistema.apellidos.label("vendedor_apellidos")
                             ).join(Producto, Venta.producto_id == Producto.id)\
                              .outerjoin(UsuarioSistema, Venta.vendedor_id == UsuarioSistema.id)\
                              .filter(Venta.id == venta_id).first()
    if not venta:
        flash("❌ Venta no encontrada", "danger")
        return redirect(url_for("ventas"))

    v = venta.Venta
    total = v.cantidad * venta.precio

    # Simulación de autorización SUNAT
    serie_numero = v.numero_comprobante or f"B001-{venta_id:06d}"
    hash_cpe = secrets.token_hex(8).upper()
    codigo_autorizacion = f"{serie_numero} | {hash_cpe}"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25*mm, leftMargin=25*mm, topMargin=25*mm, bottomMargin=25*mm)
    estilos = getSampleStyleSheet()
    elementos = []

    elementos.append(Paragraph("LIBRERÍA SALESIANA DON BOSCO", estilos['Title']))
    titulo_comp = {
        "boleta": "BOLETA DE VENTA ELECTRÓNICA",
        "factura": "FACTURA ELECTRÓNICA",
        "nota": "NOTA DE VENTA",
    }.get(v.tipo_comprobante, "COMPROBANTE DE VENTA")
    elementos.append(Paragraph(f"<b>{titulo_comp}</b> N° {serie_numero}", estilos['Heading2']))
    elementos.append(Spacer(1, 8))

    datos = [
        ["Fecha", v.fecha_venta.strftime('%d/%m/%Y %H:%M')],
        ["Cliente", v.cliente_nombre_completo or "Consumidor Final"],
        ["Documento", v.cliente_documento or "—"],
        ["Vendedor", f"{venta.vendedor_nombres or ''} {venta.vendedor_apellidos or ''}".strip() or "—"],
        ["Producto", venta.producto_nombre],
        ["Cantidad", str(v.cantidad)],
        ["Precio Unit.", f"S/ {float(venta.precio or 0):.2f}"],
        ["TOTAL", f"S/ {total:.2f}"],
    ]
    t = Table(datos, colWidths=[80*mm, 100*mm])
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#EEF2FF')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#D4AF37')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elementos.append(t)
    elementos.append(Spacer(1, 12))

    # Autorización SUNAT simulada
    autorizacion = Table([["AUTORIZACIÓN SUNAT (SIMULADA)"], [codigo_autorizacion]], colWidths=[180*mm])
    autorizacion.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#16A34A')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDF4')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    elementos.append(autorizacion)
    elementos.append(Spacer(1, 8))
    elementos.append(Paragraph("<small>Este es un comprobante de venta electrónico válido. ¡Gracias por su compra!</small>", estilos['Italic']))

    doc.build(elementos)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"comprobante_{serie_numero}.pdf", mimetype="application/pdf")

@app.route("/ver_ventas", methods=["GET", "POST"])
@login_required
@permiso_requerido("ver_reportes")
def ver_ventas():
    ventas_lista = []
    totalProductos = 0
    totalPrecio = 0
    fecha_seleccionada = request.args.get("fecha") or request.form.get("fecha")
    if fecha_seleccionada:
        fecha_obj = datetime.strptime(fecha_seleccionada, "%Y-%m-%d").date()
        ventas_lista = (
            db.session.query(
                Venta.id,
                func.concat(UsuarioSistema.nombres, " ", UsuarioSistema.apellidos).label("vendedor"),
                Producto.nombre.label("producto"),
                Venta.cantidad,
                Venta.fecha_venta,
                Producto.precio,
                (Venta.cantidad * Producto.precio).label("subtotal"),
            )
            .join(Producto, Venta.producto_id == Producto.id)
            .outerjoin(UsuarioSistema, Venta.vendedor_id == UsuarioSistema.id)
            .filter(func.date(Venta.fecha_venta) == fecha_obj)
            .order_by(Venta.id.asc())
            .all()
        )
        ventas_lista = [
            {
                "id": v.id,
                "vendedor": v.vendedor,
                "producto": v.producto,
                "cantidad": v.cantidad,
                "fecha_venta": v.fecha_venta,
                "precio": float(v.precio),
                "subtotal": float(v.subtotal),
            }
            for v in ventas_lista
        ]
        totalProductos = sum(v["cantidad"] for v in ventas_lista)
        totalPrecio = sum(v["cantidad"] * v["precio"] for v in ventas_lista)
    return render_template("ver_ventas.html", ventas=ventas_lista, totalProductos=totalProductos, totalPrecio=totalPrecio, fecha_seleccionada=fecha_seleccionada)

@app.route("/ver_productos_proveedor", methods=["GET", "POST"])
@login_required
@permiso_requerido("ver_reportes")
def ver_productos_proveedor():
    proveedores = Proveedor.query.all()
    productos = []
    proveedor_seleccionado = None
    proveedor_id = request.args.get("proveedor_id") or request.form.get("proveedor_id")
    if proveedor_id:
        proveedor_seleccionado = db.session.get(Proveedor, int(proveedor_id))
        productos = (
            db.session.query(
                Producto.id,
                Producto.nombre,
                Producto.cantidad,
                func.count(Venta.id).label("total_ventas"),
            )
            .outerjoin(Venta, Producto.id == Venta.producto_id)
            .filter(Producto.proveedor_id == proveedor_id)
            .group_by(Producto.id, Producto.nombre, Producto.cantidad)
            .all()
        )
    return render_template("ver_producto_proveedor.html", proveedores=proveedores, productos=productos, proveedor_id=int(proveedor_id) if proveedor_id else None, proveedor_seleccionado=proveedor_seleccionado)

# ===============================
# API PARA SISTEMA INTERNO
# ===============================

@app.route("/api/productos/<int:producto_id>/stock")
def api_producto_stock(producto_id):
    """API para obtener stock actual de un producto"""
    producto = Producto.query.get(producto_id)
    if not producto:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify({
        "id": producto.id,
        "stock": producto.cantidad,
        "nombre": producto.nombre
    })

@app.route("/api/productos", methods=["GET"])
@login_required
def api_listar_productos():
    productos = Producto.query.filter(Producto.cantidad > 0).all()
    return jsonify([
        {
            "id": p.id,
            "nombre": p.nombre,
            "descripcion": p.descripcion,
            "precio": p.precio,
            "imagen_url": url_for("static", filename=f"img/productos/{p.imagen}") if p.imagen else None,
        }
        for p in productos
    ])

@app.route("/api/buscar_producto")
@login_required
def api_buscar_producto():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Parámetro requerido"}), 400
    if q.isdigit():
        producto = Producto.query.get(int(q))
    else:
        producto = Producto.query.filter(Producto.nombre.like(f"%{q}%")).first()
    if producto and producto.cantidad > 0:
        return jsonify({
            "id": producto.id,
            "nombre": producto.nombre,
            "precio": float(producto.precio),
            "stock": producto.cantidad,
        })
    return jsonify({"error": "No encontrado o sin stock"}), 404

@app.route("/api/productos/top")
@login_required
def productos_top():
    top = (
        db.session.query(
            Producto.id,
            Producto.nombre,
            Producto.precio,
            func.sum(Venta.cantidad).label("total_vendido"),
        )
        .join(Venta)
        .filter(func.date(Venta.fecha_venta) == datetime.now().date())
        .group_by(Producto.id)
        .order_by(func.sum(Venta.cantidad).desc())
        .limit(10)
        .all()
    )
    return jsonify([
        {
            "id": p.id,
            "nombre": p.nombre,
            "precio": float(p.precio),
            "vendidos": p.total_vendido,
        }
        for p in top
    ])

@app.route("/api/ventas/rapida", methods=["POST"])
@login_required
def venta_rapida():
    data = request.get_json()
    items = data.get("items", [])
    if not items:
        return jsonify({"success": False, "error": "Carrito vacío"})
    try:
        for item in items:
            producto = Producto.query.get(item["id"])
            if not producto or producto.cantidad < item["cantidad"]:
                return jsonify({"success": False, "error": f'Stock insuficiente: {item["nombre"]}'})
        venta_ids = []
        total_general = 0
        cliente_rapido = None
        try:
            doc = data.get("cliente_dni", "")
            if doc:
                cliente_rapido = Cliente.query.filter(
                    or_(Cliente.dni == doc, Cliente.ruc == doc, Cliente.ce == doc)
                ).first()
        except Exception:
            cliente_rapido = None
        metodo_pago = data.get("metodo_pago", "efectivo")
        monto_recibido = None
        vuelto = None
        try:
            if metodo_pago == "efectivo":
                monto_recibido = float(data.get("monto_recibido") or 0)
        except (TypeError, ValueError):
            monto_recibido = None
        numero_pos = f"POS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        for item in items:
            producto = Producto.query.get(item["id"])
            total = float(producto.precio or 0) * int(item["cantidad"])
            nueva_venta = Venta(
                producto_id=item["id"],
                cantidad=item["cantidad"],
                vendedor_id=session["usuario_id"],
                fecha_venta=datetime.now(),
                tipo_comprobante="boleta",
                numero_comprobante=numero_pos,
                metodo_pago=metodo_pago,
                monto_recibido=monto_recibido,
                vuelto=round(float(monto_recibido) - float(total), 2) if monto_recibido is not None else None,
                cliente_nombres=data.get("cliente_nombre", ""),
                cliente_apellidos=data.get("cliente_apellido", ""),
                cliente_documento=data.get("cliente_dni", ""),
                cliente_tipo_documento=data.get("cliente_tipo_documento", ""),
                cliente_id=cliente_rapido.id if cliente_rapido else None,
            )
            db.session.add(nueva_venta)
            producto.cantidad -= item["cantidad"]
            total_general += total
            venta_ids.append(nueva_venta.id)
        db.session.commit()
        registrar_auditoria("VENTA", "ventas", f"Venta rápida POS #{venta_ids[0]} - {len(venta_ids)} item(s) - Total: S/ {total_general:.2f} ({metodo_pago})")
        try:
            verificar_stock_bajo_y_notificar()
        except Exception:
            pass
        return jsonify({
            "success": True,
            "venta_id": venta_ids[0],
            "total": float(total_general),
            "vuelto": round(float(monto_recibido) - float(total_general), 2) if monto_recibido is not None else None,
            "metodo_pago": metodo_pago,
            "numero_comprobante": numero_pos,
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})


# ===============================================
# POS TÁCTIL - VENTA RÁPIDA (tablet / mostrador)
# ===============================================

@app.route("/pos", methods=["GET"])
@login_required
def pos_tactil():
    lista_productos = Producto.query.filter(Producto.cantidad > 0).order_by(Producto.nombre).all()
    producto_datos = []
    for p in lista_productos:
        precio_mostrar = float(p.precio_oferta or p.precio or 0)
        producto_datos.append({
            "id": p.id,
            "nombre": p.nombre,
            "precio": float(p.precio or 0),
            "precio_oferta": float(p.precio_oferta) if p.precio_oferta else None,
            "precio_mostrar": precio_mostrar,
            "cantidad": p.cantidad,
            "codigo_barras": p.codigo_barras,
            "imagen_url": url_for("static", filename=f"img/productos/{p.imagen}") if p.imagen else None,
        })
    return render_template("pos_rapido.html", productos=producto_datos, now=datetime.now())


# ===============================================
# RECOMENDADOS - LOS MÁS VENDIDOS
# ===============================================

@app.route("/api/productos/recomendados")
def api_productos_recomendados():
    try:
        filas = (
            db.session.query(
                Producto.id,
                Producto.nombre,
                Producto.descripcion,
                Producto.precio,
                Producto.precio_oferta,
                Producto.cantidad,
                Producto.destacado,
                Producto.imagen,
                func.coalesce(func.sum(Venta.cantidad), 0).label("vendidos"),
            )
            .outerjoin(Venta, Venta.producto_id == Producto.id)
            .group_by(Producto.id)
            .order_by(func.sum(Venta.cantidad).desc(), Producto.destacado.desc())
            .limit(10)
            .all()
        )
        resultado = []
        for p in filas:
            resultado.append({
                "id": p.id,
                "nombre": p.nombre,
                "descripcion": p.descripcion,
                "precio": float(p.precio or 0),
                "precio_oferta": float(p.precio_oferta) if p.precio_oferta else None,
                "cantidad": p.cantidad,
                "destacado": p.destacado,
                "vendidos": int(p.vendidos or 0),
                "imagen_url": url_for("static", filename=f"img/productos/{p.imagen}") if p.imagen else None,
            })
        return jsonify(resultado)
    except Exception as e:
        print(f"❌ Error en /api/productos/recomendados: {e}")
        return jsonify([])

# ===============================
# CLIENTES (TIENDA ONLINE)
# ===============================

@app.route("/catalogo", methods=["GET"])
def catalogo_cliente():
    try:
        # Obtener el ID de categoría desde la URL
        categoria_id = request.args.get('categoria', type=int)
        
        # Obtener todas las categorías activas
        categorias = Categoria.query.filter_by(activo=True).all()
        
        # Construir la consulta de productos
        query = Producto.query.filter(Producto.cantidad > 0)
        
        # Si hay una categoría seleccionada, filtrar
        if categoria_id:
            query = query.filter(Producto.id_categoria == categoria_id)
            # Obtener el nombre de la categoría seleccionada para mostrarlo
            categoria_seleccionada = Categoria.query.get(categoria_id)
        else:
            categoria_seleccionada = None
        
        # Ejecutar la consulta
        productos = query.order_by(Producto.nombre.asc()).all()
        
        # Renderizar la plantilla con los datos
        return render_template("catalogo_cliente.html", 
                              categorias=categorias,
                              productos=productos,
                              categoria_seleccionada=categoria_seleccionada,
                              categoria_id=categoria_id)
    except Exception as e:
        print(f"❌ Error en /catalogo: {e}")
        import traceback
        traceback.print_exc()
        return render_template("catalogo_cliente.html", 
                              categorias=[], 
                              productos=[],
                              categoria_seleccionada=None,
                              categoria_id=None)

@app.route("/api/productos/catalogo")
def api_productos_catalogo():
    try:
        q = request.args.get('q', '')
        categoria_id = request.args.get('categoria', type=int)
        
        query = Producto.query.filter(Producto.cantidad > 0)
        
        if q:
            query = query.filter(Producto.nombre.like(f'%{q}%'))
        if categoria_id:
            query = query.filter_by(id_categoria=categoria_id)
        
        productos = query.all()
        
        resultado = []
        for p in productos:
            try:
                # Obtener nombre de categoría de forma segura
                categoria_nombre = None
                if hasattr(p, 'categoria_rel') and p.categoria_rel:
                    categoria_nombre = p.categoria_rel.nombre
                
                resultado.append({
                    "id": p.id,
                    "nombre": p.nombre,
                    "descripcion": p.descripcion,
                    "precio": float(p.precio) if p.precio else 0,
                    "precio_oferta": float(p.precio_oferta) if p.precio_oferta else None,
                    "categoria_id": p.id_categoria,
                    "categoria_nombre": categoria_nombre,
                    "cantidad": p.cantidad,
                    "destacado": p.destacado,
                    "imagen_url": url_for("static", filename=f"img/productos/{p.imagen}") if p.imagen else None,
                })
            except Exception as e:
                print(f"Error procesando producto {p.id}: {e}")
                continue
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Error en /api/productos/catalogo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "detalle": "Error interno del servidor"}), 500



@app.route("/logout-cliente")
def logout_cliente():
    session.clear()
    flash("✅ Sesión cerrada", "success")
    return redirect("/catalogo")

@app.route("/registro-cliente", methods=["GET", "POST"])
def registro_cliente():
    if request.method == "POST":
        try:
            def _nulo(valor):
                """Convierte cadenas vacías en None (NULL) para columnas únicas/opcionales."""
                return valor.strip() if valor and valor.strip() else None

            # Ubigeo de residencia OBLIGATORIO (departamento -> provincia -> distrito)
            ubigeo = {
                "departamento": _nulo(request.form.get("departamento")),
                "provincia": _nulo(request.form.get("provincia")),
                "distrito": _nulo(request.form.get("distrito")),
            }
            if not all(ubigeo.values()):
                flash("❌ Debes indicar tu lugar de residencia: departamento, provincia y distrito", "danger")
                return redirect(url_for("registro_cliente"))

            tipo_documento = request.form.get("tipo_documento", "DNI")
            numero_documento = _nulo(request.form.get("numero_documento"))

            # Delegación al microservicio dueño de datos (librospe_ms_clientes)
            # Gateway NO escribe directo a librospe_db; el microservicio es la fuente de verdad.
            payload = {
                "email": request.form["email"].strip(),
                "nombres": request.form["nombres"].strip(),
                "apellidos": request.form["apellidos"].strip(),
                "clave": request.form["clave"],
                "telefono": armar_telefono(request.form.get("prefijo"), request.form.get("telefono")),
                "direccion": _nulo(request.form.get("direccion")),
                "departamento": ubigeo["departamento"],
                "provincia": ubigeo["provincia"],
                "distrito": ubigeo["distrito"],
                "tipo_documento": tipo_documento,
                "numero_documento": numero_documento,
            }
            data = json.dumps(payload).encode("utf-8")
            url = app.config["MS_CLIENTES_URL"].rstrip("/") + "/"
            req = Request(url, data=data, headers={
                "Content-Type": "application/json",
                "X-Service-Token": app.config["SERVICE_TOKEN"],
            }, method="POST")
            try:
                with urlopen(req, timeout=10) as resp:
                    body = resp.read().decode("utf-8")
                    # 201 creado
                    flash("✅ Registro exitoso", "success")
                    return redirect(url_for("login_cliente"))
            except HTTPError as he:
                err_body = he.read().decode("utf-8", errors="replace")
                try:
                    err_json = json.loads(err_body)
                    msg = err_json.get("error", err_body)
                except Exception:
                    msg = err_body or str(he)
                if he.code == 409:
                    flash(f"❌ {msg}", "danger")
                    return redirect(url_for("registro_cliente"))
                flash(f"❌ Error microservicio clientes ({he.code}): {msg}", "danger")
                return redirect(url_for("registro_cliente"))
            except URLError as ue:
                # Fallback producción AlwaysData (gateway único sin 4 procesos): escribe directo al bind clientes
                # No vuelve a librospe_db; escribe a librospe_ms_clientes (dueño de datos)
                try:
                    engine_clientes = None
                    try:
                        engine_clientes = db.get_engine(bind="clientes")
                    except Exception:
                        # Flask-SQLAlchemy 3.x: db.engines dict
                        engine_clientes = db.engines.get("clientes") if hasattr(db, "engines") else None
                    if engine_clientes is None:
                        raise RuntimeError("Bind clientes no disponible")
                    # Verifica duplicado en la BD del microservicio (no en librospe_db)
                    existe_ms = db.session.execute(
                        text("SELECT id FROM clientes WHERE correo=:c"),
                        {"c": payload["email"]},
                        bind_arguments={"bind": engine_clientes}
                    ).scalar()
                    if existe_ms:
                        flash("❌ El correo ya está registrado", "danger")
                        return redirect(url_for("registro_cliente"))
                    hashed = bcrypt.generate_password_hash(payload["clave"]).decode("utf-8")
                    dni_f = payload["numero_documento"] if payload["tipo_documento"] == "DNI" else None
                    ce_f = payload["numero_documento"] if payload["tipo_documento"] == "CE" else None
                    db.session.execute(text("""
                        INSERT INTO clientes (dni, ce, nombres, apellidos, correo, telefono, direccion,
                                              departamento, provincia, distrito, clave, estado)
                        VALUES (:dni, :ce, :nombres, :apellidos, :correo, :telefono, :direccion,
                                :departamento, :provincia, :distrito, :clave, 1)
                    """), {
                        "dni": dni_f, "ce": ce_f, "nombres": payload["nombres"], "apellidos": payload["apellidos"],
                        "correo": payload["email"], "telefono": payload["telefono"], "direccion": payload["direccion"],
                        "departamento": payload["departamento"], "provincia": payload["provincia"],
                        "distrito": payload["distrito"], "clave": hashed
                    }, bind_arguments={"bind": engine_clientes})
                    db.session.commit()
                    flash("✅ Registro exitoso", "success")
                    return redirect(url_for("login_cliente"))
                except Exception as e2:
                    db.session.rollback()
                    flash(f"❌ Error al registrar. Intenta nuevamente.", "danger")
                    return redirect(url_for("registro_cliente"))
        except Exception as e:
            flash(f"❌ Error: {str(e)}", "danger")
    return render_template("registro_cliente.html")

@app.route("/api/departamentos")
def api_departamentos():
    """Lista de departamentos para el formulario de registro."""
    datos = Departamento.query.order_by(Departamento.nombre).all()
    return jsonify([{"id": d.id, "nombre": d.nombre} for d in datos])

@app.route("/api/provincias/<int:departamento_id>")
def api_provincias(departamento_id):
    """Provincias de un departamento."""
    datos = Provincia.query.filter_by(departamento_id=departamento_id).order_by(Provincia.nombre).all()
    return jsonify([{"id": p.id, "nombre": p.nombre} for p in datos])

@app.route("/api/distritos/<int:provincia_id>")
def api_distritos(provincia_id):
    """Distritos de una provincia."""
    datos = Distrito.query.filter_by(provincia_id=provincia_id).order_by(Distrito.nombre).all()
    return jsonify([{"id": d.id, "nombre": d.nombre} for d in datos])

@app.route("/cliente/perfil")
@login_required_cliente
def cliente_perfil():
    cliente = _obtener_cliente_por_id(session["cliente_id"])
    if not cliente:
        flash("❌ Cliente no encontrado", "danger")
        return redirect(url_for("logout_cliente"))
    return render_template("cliente_perfil.html", cliente=cliente)

@app.route("/cliente/actualizar-perfil", methods=["POST"])
@login_required_cliente
def cliente_actualizar_perfil():
    try:
        cliente = _obtener_cliente_por_id(session["cliente_id"])
        if not cliente:
            flash("❌ Cliente no encontrado", "danger")
            return redirect(url_for("cliente_perfil"))

        # Ubigeo de residencia OBLIGATORIO (departamento -> provincia -> distrito)
        nuevo_departamento = (request.form.get("departamento") or "").strip()
        nueva_provincia = (request.form.get("provincia") or "").strip()
        nuevo_distrito = (request.form.get("distrito") or "").strip()
        if not (nuevo_departamento and nueva_provincia and nuevo_distrito):
            flash("❌ Debes indicar tu lugar de residencia: departamento, provincia y distrito", "danger")
            return redirect(url_for("cliente_perfil"))

        nuevos_nombres = request.form.get("nombres", "").strip()
        nuevos_apellidos = request.form.get("apellidos", "").strip()
        nuevo_telefono = armar_telefono(request.form.get("prefijo"), request.form.get("telefono"))
        nueva_direccion = (request.form.get("direccion") or "").strip() or None
        nuevo_email = (request.form.get("email") or "").strip()
        tipo_documento = request.form.get("tipo_documento", "DNI")
        numero_documento = (request.form.get("numero_documento") or "").strip() or None
        nuevo_dni = numero_documento if tipo_documento != "CE" else None
        nuevo_ce = numero_documento if tipo_documento == "CE" else None

        if nuevo_email != cliente.correo:
            existe = _obtener_cliente_por_correo(nuevo_email)
            if existe:
                flash("❌ El correo ya está registrado", "danger")
                return redirect(url_for("cliente_perfil"))

        # Producción real: actualiza en microservicio si es MS, sino en librospe_db
        is_ms = getattr(cliente, "_is_ms", False)
        if is_ms:
            try:
                engine = db.get_engine(bind="clientes")
            except Exception:
                engine = db.engines.get("clientes") if hasattr(db, "engines") else None
            db.session.execute(text("""
                UPDATE clientes SET nombres=:nombres, apellidos=:apellidos, telefono=:telefono,
                    direccion=:direccion, departamento=:departamento, provincia=:provincia,
                    distrito=:distrito, correo=:correo, dni=:dni, ce=:ce
                WHERE id=:id
            """), {
                "nombres": nuevos_nombres, "apellidos": nuevos_apellidos, "telefono": nuevo_telefono,
                "direccion": nueva_direccion, "departamento": nuevo_departamento, "provincia": nueva_provincia,
                "distrito": nuevo_distrito, "correo": nuevo_email, "dni": nuevo_dni, "ce": nuevo_ce, "id": cliente.id
            }, bind_arguments={"bind": engine})
            db.session.commit()
        else:
            # Fallback cliente antiguo en librospe_db (ORM)
            orm = Cliente.query.get(cliente.id)
            orm.nombres = nuevos_nombres; orm.apellidos = nuevos_apellidos
            orm.telefono = nuevo_telefono; orm.direccion = nueva_direccion
            orm.departamento = nuevo_departamento; orm.provincia = nueva_provincia; orm.distrito = nuevo_distrito
            orm.correo = nuevo_email; orm.dni = nuevo_dni; orm.ce = nuevo_ce
            db.session.commit()

        session["cliente_correo"] = nuevo_email
        if numero_documento:
            session["cliente_dni"] = numero_documento
        else:
            session.pop("cliente_dni", None)
        
        session["cliente_nombres"] = nuevos_nombres
        session["cliente_apellidos"] = nuevos_apellidos
        session["cliente_telefono"] = nuevo_telefono
        session["cliente_direccion"] = nueva_direccion
        
        flash("✅ Perfil actualizado", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")
    
    return redirect(url_for("cliente_perfil"))

@app.route("/cliente/cambiar-contrasena", methods=["GET", "POST"])
@login_required_cliente
def cliente_cambiar_contrasena():
    if request.method == "POST":
        contrasena_actual = request.form.get("contrasena_actual")
        nueva_contrasena = request.form.get("nueva_contrasena")
        confirmar_contrasena = request.form.get("confirmar_contrasena")

        if not contrasena_actual or not nueva_contrasena or not confirmar_contrasena:
            flash("❌ Todos los campos son obligatorios", "danger")
            return redirect(url_for("cliente_cambiar_contrasena"))

        if nueva_contrasena != confirmar_contrasena:
            flash("❌ Las contraseñas no coinciden", "danger")
            return redirect(url_for("cliente_cambiar_contrasena"))

        if len(nueva_contrasena) < 6:
            flash("❌ La contraseña debe tener al menos 6 caracteres", "danger")
            return redirect(url_for("cliente_cambiar_contrasena"))

        cliente = _obtener_cliente_por_id(session["cliente_id"])
        if not cliente:
            flash("❌ Cliente no encontrado", "danger")
            return redirect(url_for("cliente_cambiar_contrasena"))

        if not bcrypt.check_password_hash(cliente.clave, contrasena_actual):
            flash("❌ Contraseña actual incorrecta", "danger")
            return redirect(url_for("cliente_cambiar_contrasena"))

        try:
            nueva_clave_hash = bcrypt.generate_password_hash(nueva_contrasena).decode("utf-8")
            if getattr(cliente, "_is_ms", False):
                try:
                    engine = db.get_engine(bind="clientes")
                except Exception:
                    engine = db.engines.get("clientes") if hasattr(db, "engines") else None
                db.session.execute(text("UPDATE clientes SET clave=:clave WHERE id=:id"),
                    {"clave": nueva_clave_hash, "id": cliente.id}, bind_arguments={"bind": engine})
            else:
                orm = Cliente.query.get(cliente.id)
                orm.clave = nueva_clave_hash
            db.session.commit()
            flash("✅ Contraseña actualizada", "success")
            return redirect("/catalogo")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {str(e)}", "danger")
    
    return render_template("cliente_cambiar_contrasena.html")

# ===============================
# RECUPERACIÓN DE CONTRASEÑA
# ===============================

@app.route("/recuperar-contrasena", methods=["GET", "POST"])
def recuperar_contrasena():
    if request.method == "POST":
        email = request.form.get("email")
        
        if not email:
            flash("❌ Ingresa tu correo electrónico", "danger")
            return redirect(url_for("recuperar_contrasena"))
        
        cliente = Cliente.query.filter_by(correo=email).first()
        
        if cliente:
            token = generar_token_recuperacion()
            cliente.token_recuperacion = token
            cliente.token_expiracion = datetime.now() + timedelta(hours=1)
            db.session.commit()
            
            enlace = url_for("resetear_contrasena", token=token, _external=True)
            flash(f"✅ Enlace de recuperación: {enlace}", "info")
        else:
            flash("✅ Si el correo está registrado, recibirás un enlace", "success")
        
        return redirect(url_for("login_cliente"))
    
    return render_template("recuperar_contrasena.html")

@app.route("/resetear-contrasena/<token>", methods=["GET", "POST"])
def resetear_contrasena(token):
    cliente = Cliente.query.filter_by(token_recuperacion=token).first()
    
    if not cliente:
        flash("❌ Enlace inválido o ya utilizado", "danger")
        return redirect(url_for("login_cliente"))
    
    if cliente.token_expiracion < datetime.now():
        flash("❌ El enlace ha expirado", "danger")
        return redirect(url_for("recuperar_contrasena"))
    
    if request.method == "POST":
        nueva = request.form.get("nueva")
        confirmar = request.form.get("confirmar")
        
        if not nueva or not confirmar:
            flash("❌ Todos los campos son obligatorios", "danger")
            return render_template("resetear_contrasena.html", token=token)
        
        if nueva != confirmar:
            flash("❌ Las contraseñas no coinciden", "danger")
            return render_template("resetear_contrasena.html", token=token)
        
        if len(nueva) < 6:
            flash("❌ La contraseña debe tener al menos 6 caracteres", "danger")
            return render_template("resetear_contrasena.html", token=token)
        
        try:
            nueva_clave_hash = bcrypt.generate_password_hash(nueva).decode("utf-8")
            cliente.clave = nueva_clave_hash
            cliente.token_recuperacion = None
            cliente.token_expiracion = None
            db.session.commit()
            
            flash("✅ Contraseña actualizada", "success")
            return redirect(url_for("login_cliente"))
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {str(e)}", "danger")
    
    return render_template("resetear_contrasena.html", token=token)

# ===============================
# PEDIDOS
# ===============================

@app.route("/carrito")
def ver_carrito():
    return render_template("carrito.html")

@app.route("/checkout")
@login_required_cliente
def checkout():
    # Cliente: microservicio dueño primero (bind clientes), fallback librospe_db
    cid = session.get("cliente_id")
    _asegurar_cliente_en_principal(cid)
    cliente = _obtener_cliente_por_id(cid)
    
    # Pasar datos del cliente al template
    return render_template("checkout.html", 
                          cliente=cliente,
                          datetime=datetime)

@app.route("/pago")
@login_required_cliente
def pago():
    # Obtener datos del checkout desde localStorage (vía sesión o query params)
    # Por ahora simplemente renderizamos la plantilla
    return render_template("pago.html", datetime=datetime)

@app.route("/mis-pedidos")
@login_required_cliente
def mis_pedidos():
    pedidos = Pedido.query.filter_by(cliente_id=session["cliente_id"]).order_by(Pedido.fecha_pedido.desc()).all()
    return render_template("mis_pedidos.html", pedidos=pedidos)

@app.route("/pedidos/confirmar-recepcion/<int:pedido_id>", methods=["POST"])
@login_required_cliente
def confirmar_recepcion_pedido(pedido_id):
    """El cliente confirma que recibió su pedido delivery."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    pedido = Pedido.query.get_or_404(pedido_id)

    if pedido.cliente_id != session.get("cliente_id"):
        if is_ajax:
            return jsonify({"success": False, "error": "No autorizado"}), 403
        flash("❌ No tienes permiso para confirmar este pedido", "danger")
        return redirect(url_for("mis_pedidos"))

    if pedido.tipo_entrega != "delivery":
        if is_ajax:
            return jsonify({"success": False, "error": "Este pedido no fue despachado por delivery"}), 400
        flash("❌ Este pedido no fue despachado por delivery", "danger")
        return redirect(url_for("mis_pedidos"))

    if pedido.estado != "entregado":
        if is_ajax:
            return jsonify({"success": False, "error": "El pedido aún no está marcado como entregado"}), 400
        flash("❌ El pedido aún no está marcado como entregado", "danger")
        return redirect(url_for("mis_pedidos"))

    if pedido.cliente_confirmo:
        if is_ajax:
            return jsonify({"success": False, "error": "Ya confirmaste la recepción de este pedido"}), 400
        flash("✅ Ya habías confirmado la recepción de este pedido", "info")
        return redirect(url_for("mis_pedidos"))

    pedido.cliente_confirmo = 1
    pedido.fecha_confirmacion_cliente = datetime.now()
    db.session.commit()

    print(f"✅ Cliente confirmó recepción del pedido #{pedido_id} ({datetime.now()})")

    if is_ajax:
        return jsonify({"success": True, "message": "¡Gracias por confirmar la recepción!"})

    flash("✅ ¡Gracias por confirmar la recepción de tu pedido!", "success")
    return redirect(url_for("mis_pedidos"))

@app.route("/api/mis-pedidos")
@login_required_cliente
def api_mis_pedidos():
    pedidos = Pedido.query.filter_by(cliente_id=session["cliente_id"]).order_by(Pedido.fecha_pedido.desc()).all()
    return jsonify([
        {
            "id": p.id,
            "fecha_pedido": p.fecha_pedido.strftime("%d/%m/%Y %H:%M"),
            "estado": p.estado,
            "total": float(p.total),
            "tipo_entrega": p.tipo_entrega,
        }
        for p in pedidos
    ])

def _punto_entrega_pedido(data, cliente_direccion, cliente_residencia):
    """Punto (lat, lng, precision) para un pedido de delivery.

    Prioriza la ubicación exacta que el cliente marcó en el mapa del carrito
    (llega como 'latitud'/'longitud' en el payload). Si no vino, geocodifica el
    texto de la dirección como respaldo. Devuelve (None, None, None) cuando no
    es delivery o no se pudo ubicar (el admin lo fija a mano).
    """
    if (data or {}).get("tipo_entrega") != "delivery":
        return None, None, None

    lat_cliente = str((data or {}).get("latitud") or "").strip()
    lng_cliente = str((data or {}).get("longitud") or "").strip()
    if _coordenadas_validas(lat_cliente, lng_cliente):
        # La ubicación que el cliente ve y marca en el mapa es la que manda.
        return float(lat_cliente), float(lng_cliente), "exacta"

    if cliente_direccion:
        return geocodificar_direccion(
            cliente_direccion,
            getattr(cliente_residencia, "departamento", None),
            getattr(cliente_residencia, "provincia", None),
            getattr(cliente_residencia, "distrito", None),
        )
    return None, None, None


@app.route("/api/pedidos/crear", methods=["POST"])
@login_required_cliente
def crear_pedido():
    data = request.get_json()
    
    print("=" * 60)
    print("📦 DATOS RECIBIDOS EN /api/pedidos/crear:")
    print(f"Items: {len(data.get('items', []))} productos")
    print(f"Tipo entrega: {data.get('tipo_entrega')}")
    print(f"Total: {data.get('total')}")
    print(f"Cliente data completo: {data.get('cliente', {})}")
    print(f"Documento: {data.get('cliente', {}).get('documento', 'NO ENCONTRADO')}")
    print(f"Razón Social: {data.get('cliente', {}).get('razon_social', 'NO')}")
    print(f"Dirección Fiscal: {data.get('cliente', {}).get('direccion_fiscal', 'NO')}")
    print("=" * 60)
    
    try:
        # ============================================
        # 1. VALIDAR STOCK
        # ============================================
        for item in data["items"]:
            producto = Producto.query.get(item["id"])
            if not producto:
                return jsonify({"success": False, "error": f'Producto no encontrado: {item["nombre"]}'})
            if producto.cantidad < item["cantidad"]:
                return jsonify({"success": False, "error": f'Stock insuficiente: {item["nombre"]}. Disponible: {producto.cantidad}'})
        
        # ============================================
        # 2. EXTRAER DATOS DEL CHECKOUT
        # ============================================
        cliente_data = data.get("cliente", {})
        
        # Datos personales
        cliente_nombres = cliente_data.get("nombres", "").strip()
        cliente_apellidos = cliente_data.get("apellidos", "").strip()
        cliente_email = cliente_data.get("email", "").strip()
        cliente_telefono = cliente_data.get("telefono", "").strip()
        
        # Documento (DNI o RUC)
        cliente_documento = cliente_data.get("documento", "").strip()
        if not cliente_documento:
            cliente_documento = cliente_data.get("dni", "").strip()
        if not cliente_documento:
            cliente_documento = cliente_data.get("ruc", "").strip()
        
        # Datos de facturación (para RUC)
        cliente_razon_social = cliente_data.get("razon_social", "").strip()
        cliente_direccion_fiscal = cliente_data.get("direccion_fiscal", "").strip()  # ← AGREGAR

        # Tipo de documento (DNI / Carnet de Extranjería / RUC)
        cliente_tipo_documento = cliente_data.get("tipo_documento", "").strip()
        
        # Dirección de entrega
        cliente_direccion = data.get("direccion", "").strip()
        
        # Fallback a sesión si es necesario
        if not cliente_nombres:
            cliente_nombres = session.get("cliente_nombres", "")
        if not cliente_apellidos:
            cliente_apellidos = session.get("cliente_apellidos", "")
        if not cliente_email:
            cliente_email = session.get("cliente_email", "")
        if not cliente_telefono:
            cliente_telefono = session.get("cliente_telefono", "")
        if not cliente_documento:
            cliente_documento = session.get("cliente_dni", "")
        
        print(f"\n📝 DATOS A GUARDAR EN VENTA:")
        print(f"   Nombres: '{cliente_nombres}'")
        print(f"   Apellidos: '{cliente_apellidos}'")
        print(f"   Email: '{cliente_email}'")
        print(f"   Teléfono: '{cliente_telefono}'")
        print(f"   Documento (DNI/RUC): '{cliente_documento}'")
        print(f"   Razón Social: '{cliente_razon_social}'")
        print(f"   Dirección Fiscal: '{cliente_direccion_fiscal}'")
        print(f"   Dirección Entrega: '{cliente_direccion}'")
        
        # ============================================
        # 2.5 VALIDAR DELIVERY (dirección + distrito de residencia)
        # ============================================
        cliente_residencia = None
        if data.get("tipo_entrega") == "delivery":
            if not cliente_direccion:
                return jsonify({"success": False, "error": "Ingresa tu dirección de entrega."})
            cliente_residencia = _obtener_cliente_por_id(session["cliente_id"])
            if not cliente_residencia or not all(
                [cliente_residencia.departamento, cliente_residencia.provincia, cliente_residencia.distrito]
            ):
                return jsonify({
                    "success": False,
                    "error": "Completa tu lugar de residencia (departamento, provincia y distrito) en Mi Perfil para poder usar el delivery."
                })
        
        # ============================================
        # 3. CREAR PEDIDO
        # ============================================
        # FK pedidos.cliente_id -> librospe_db.clientes: el cliente pudo
        # registrarse solo en el microservicio, asegura la fila en la principal.
        _asegurar_cliente_en_principal(session["cliente_id"])

        # Punto en el mapa: prioriza la ubicación exacta que el cliente marcó
        # en el mapa del carrito; si no llegó, geocodifica la dirección como
        # respaldo. Nunca tumba el pedido.
        lat_entrega, lng_entrega, precision_entrega = _punto_entrega_pedido(
            data, cliente_direccion, cliente_residencia)

        pedido = Pedido(
            cliente_id=session["cliente_id"],
            total=float(data["total"]),
            tipo_entrega=data["tipo_entrega"],
            direccion_entrega=cliente_direccion if data["tipo_entrega"] == "delivery" else "",
            lat=lat_entrega,
            lng=lng_entrega,
            geo_precision=precision_entrega,
        )
        db.session.add(pedido)
        db.session.flush()
        
        # ============================================
        # 4. CREAR DETALLES Y VENTAS
        # ============================================
        # Número de comprobante correlativo (B001-000123 / F001-000045 / NV001-000123)
        # Se calcula POR ITEM: si se calcula una sola vez antes del bucle,
        # todos los productos de un pedido se guardan con el MISMO numero.
        tipo_comp = data.get("comprobante", {}).get("tipo", "boleta") or "boleta"
        if tipo_comp not in ("boleta", "factura", "nota"):
            tipo_comp = "boleta"
        serie = {"boleta": "B001", "factura": "F001", "nota": "NV001"}.get(tipo_comp, "NV001")
        contador_base = Venta.query.filter_by(tipo_comprobante=tipo_comp).count()
        
        productos_para_correo = []
        
        cliente_obj = _obtener_cliente_por_id(session["cliente_id"])
        
        for item in data["items"]:
            numero_comprobante = f"{serie}-{contador_base + 1:06d}"
            contador_base += 1
            producto = Producto.query.get(item["id"])
            subtotal = float(item["precio"]) * int(item["cantidad"])
            
            # Detalle del pedido
            detalle = DetallePedido(
                pedido_id=pedido.id,
                producto_id=item["id"],
                cantidad=int(item["cantidad"]),
                precio_unitario=float(item["precio"]),
                subtotal=subtotal,
            )
            db.session.add(detalle)
            
            # Actualizar stock
            producto.cantidad -= int(item["cantidad"])
            
            # Crear VENTA (guardar dirección fiscal en cliente_direccion o campo específico)
            venta = Venta(
                producto_id=item["id"],
                cantidad=int(item["cantidad"]),
                vendedor_id=1,
                fecha_venta=datetime.now(),
                tipo_comprobante=tipo_comp,
                numero_comprobante=numero_comprobante,
                pedido_id=pedido.id,
                cliente_nombres=cliente_nombres,
                cliente_apellidos=cliente_apellidos,
                cliente_documento=cliente_documento,
                cliente_tipo_documento=cliente_tipo_documento or None,
                cliente_email=cliente_email,
                cliente_direccion=cliente_direccion,
                cliente_direccion_fiscal=cliente_direccion_fiscal,  # ← NUEVO: dirección fiscal
                cliente_razon_social=cliente_razon_social,          # ← NUEVO: razón social
                cliente_id=cliente_obj.id if cliente_obj else None,
            )
            db.session.add(venta)
            
            productos_para_correo.append({
                'nombre': producto.nombre,
                'cantidad': int(item["cantidad"]),
                'precio_unitario': float(item["precio"]),
                'total': subtotal
            })
        
        # ============================================
        # 4.5 ACTUALIZAR PERFIL DEL CLIENTE (recomendación)
        # Guarda el DNI/RUC y completa nombres si están vacíos
        # ============================================
        if cliente_obj:
            campos = {}
            if not cliente_obj.dni and cliente_documento and len(cliente_documento) == 8 and cliente_documento.isdigit():
                campos["dni"] = cliente_documento
            elif not cliente_obj.ce and cliente_documento and len(cliente_documento) == 9 and not cliente_documento.isdigit():
                campos["ce"] = cliente_documento
            if not cliente_obj.nombres and cliente_nombres:
                campos["nombres"] = cliente_nombres
            if not cliente_obj.apellidos and cliente_apellidos:
                campos["apellidos"] = cliente_apellidos
            if campos:
                _guardar_datos_cliente(session["cliente_id"], campos)
        
        db.session.commit()
        
        print(f"\n✅ PEDIDO #{pedido.id} COMPLETADO")
        print(f"   Cliente: {cliente_nombres} {cliente_apellidos}")
        print(f"   Documento: '{cliente_documento}'")
        if cliente_razon_social:
            print(f"   Razón Social: '{cliente_razon_social}'")
        if cliente_direccion_fiscal:
            print(f"   Dirección Fiscal: '{cliente_direccion_fiscal}'")
        
        # ============================================
        # 5. ENTREGA DEL COMPROBANTE: correo o WhatsApp
        # ============================================
        # Si el cliente no tiene correo (o no es válido), el comprobante
        # se ofrece por WhatsApp al celular registrado.
        etiq_comp = {"boleta": "Boleta de venta", "factura": "Factura", "nota": "Nota de venta"}.get(tipo_comp, "Comprobante")
        texto_wa = (
            f"📚 Librería Salesiana Don Bosco\n"
            f"{etiq_comp} N° {numero_comprobante}\n"
            f"Cliente: {(cliente_nombres + ' ' + cliente_apellidos).strip() or 'Cliente'}\n"
            f"Total: S/ {float(data['total']):.2f}\n"
            f"Gracias por tu compra."
        )
        correo_enviado = False
        if cliente_email and "@" in cliente_email:
            try:
                correo_enviado = bool(enviar_comprobante_email(
                    destinatario=cliente_email,
                    cliente_nombre=f"{cliente_nombres} {cliente_apellidos}".strip(),
                    tipo_comprobante=tipo_comp,
                    numero_comprobante=numero_comprobante,
                    fecha=datetime.now(),
                    productos=productos_para_correo,
                    total_venta=float(data["total"]),
                    documento=cliente_documento,
                    tipo_documento="RUC" if tipo_comp == "factura" else (cliente_tipo_documento or ("DNI" if cliente_documento else "")),
                    razon_social=cliente_razon_social,
                    direccion_fiscal=cliente_direccion_fiscal,
                ))
                print(f"📧 Correo enviado a {cliente_email}")
            except Exception as e:
                print(f"⚠️ Error al enviar correo: {e}")

        whatsapp_url = None
        if not correo_enviado:
            whatsapp_url = enlace_whatsapp(cliente_telefono, texto_wa)
            if whatsapp_url:
                print(f"💬 Comprobante disponible por WhatsApp a {cliente_telefono}")

        return jsonify({
            "success": True,
            "pedido_id": pedido.id,
            "numero_comprobante": numero_comprobante,
            "tipo_comprobante": tipo_comp,
            "correo_enviado": correo_enviado,
            "whatsapp_url": whatsapp_url,
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

@app.route("/pedidos")
@login_required
def ver_pedidos():
    es_admin = session.get("rol") == "administrador"
    
    # ============================================
    # OBTENER PARÁMETROS DE FILTRO
    # ============================================
    search = request.args.get('search', '').strip()
    estado_filter = request.args.get('estado', '').strip()
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()
    
    # ============================================
    # CONTADORES CORRECTOS
    # ============================================
    total_pedidos = db.session.execute(text(
        "SELECT COUNT(*) FROM pedidos WHERE estado != 'cancelado'"
    )).scalar() or 0
    
    pedidos_pendientes = db.session.execute(text(
        "SELECT COUNT(*) FROM pedidos WHERE estado = 'pendiente'"
    )).scalar() or 0
    
    pedidos_completados = db.session.execute(text(
        "SELECT COUNT(*) FROM pedidos WHERE estado IN ('entregado', 'recogido')"
    )).scalar() or 0
    
    pedidos_en_proceso = db.session.execute(text(
        "SELECT COUNT(*) FROM pedidos WHERE estado IN ('confirmado', 'preparando', 'enviado', 'listo_tienda')"
    )).scalar() or 0
    
    # ============================================
    # CONSULTA CON FILTROS
    # ============================================
    query = db.session.query(
        Pedido.id,
        Pedido.fecha_pedido,
        Pedido.estado,
        Pedido.total,
        Pedido.tipo_entrega,
        Pedido.direccion_entrega,
        Cliente.nombres.label("cliente_nombres"),
        Cliente.apellidos.label("cliente_apellidos"),
        Cliente.correo.label("cliente_email"),
        Cliente.telefono.label("cliente_telefono"),
    ).join(Cliente, Pedido.cliente_id == Cliente.id)
    
    # Aplicar filtros
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Pedido.id.cast(db.String).like(search_term),
                Cliente.nombres.like(search_term),
                Cliente.apellidos.like(search_term),
                Cliente.correo.like(search_term)
            )
        )
    
    if estado_filter:
        query = query.filter(Pedido.estado == estado_filter)
    else:
        # Si no hay filtro de estado, excluir cancelados
        query = query.filter(Pedido.estado != 'cancelado')
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            query = query.filter(func.date(Pedido.fecha_pedido) >= fecha_desde_obj)
        except:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            query = query.filter(func.date(Pedido.fecha_pedido) <= fecha_hasta_obj)
        except:
            pass
    
    pedidos = query.order_by(Pedido.fecha_pedido.desc()).all()
    
    pedidos_lista = []
    for p in pedidos:
        pedidos_lista.append({
            "id": p.id,
            "fecha_pedido": p.fecha_pedido,
            "estado": p.estado,
            "total": float(p.total) if p.total else 0,
            "tipo_entrega": p.tipo_entrega,
            "direccion_entrega": p.direccion_entrega,
            "cliente_nombres": p.cliente_nombres,
            "cliente_apellidos": p.cliente_apellidos,
            "cliente_nombre_completo": f"{p.cliente_nombres or ''} {p.cliente_apellidos or ''}".strip(),
            "cliente_email": p.cliente_email,
            "cliente_telefono": p.cliente_telefono,
        })
    
    # ============================================
    # OBTENER LISTA DE ESTADOS PARA EL FILTRO
    # ============================================
    estados_disponibles = db.session.execute(
        text("SELECT DISTINCT estado FROM pedidos ORDER BY estado")
    ).fetchall()
    estados_lista = [e[0] for e in estados_disponibles]
    
    return render_template("pedidos.html", 
                          pedidos=pedidos_lista,
                          total_pedidos=total_pedidos,
                          pedidos_pendientes=pedidos_pendientes,
                          pedidos_completados=pedidos_completados,
                          pedidos_en_proceso=pedidos_en_proceso,
                          es_admin=es_admin,
                          search=search,
                          estado_filter=estado_filter,
                          fecha_desde=fecha_desde,
                          fecha_hasta=fecha_hasta,
                          estados=estados_lista,
                          datetime=datetime)


# ========================================================================
# DELIVERY: MAPA DE PUNTOS DE ENTREGA
# Geocodifica con Nominatim (OpenStreetMap), sin clave ni costo.
# ========================================================================

# Fallback: centro del Perú si no se configuró la tienda en el entorno.
LAT_LIMITE = (-18.40, -0.05)
LNG_LIMITE = (-81.35, -68.65)
URL_NOMINATIM = "https://nominatim.openstreetmap.org/search"


def _coordenadas_validas(lat, lng):
    """True si el punto cae dentro de un rango razonable para el Perú."""
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return False
    return (LAT_LIMITE[0] <= lat <= LAT_LIMITE[1]
            and LNG_LIMITE[0] <= lng <= LNG_LIMITE[1])


def _consultar_nominatim(consulta):
    """Una consulta a Nominatim. Devuelve (lat, lng) o (None, None)."""
    url = (f"{URL_NOMINATIM}?format=jsonv2&limit=1&countrycodes=pe"
           f"&q={quote_plus(consulta)}")
    try:
        peticion = Request(url, headers={
            # Nominatim exige identificar el cliente en su User-Agent.
            "User-Agent": os.environ.get(
                "MAPA_USER_AGENT", "LibreriaSalesiana/1.0 (proyecto academico)"),
            "Accept-Language": "es",
        })
        with urlopen(peticion, timeout=4) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        if datos:
            lat, lng = datos[0].get("lat"), datos[0].get("lon")
            if _coordenadas_validas(lat, lng):
                return float(lat), float(lng)
    except Exception as e:
        # Incluye timeouts: el checkout no puede depender de un tercero.
        print(f"[mapa] Nominatim fallo en '{consulta[:60]}': {e}")
    return None, None


def geocodificar_direccion(direccion, departamento=None, provincia=None, distrito=None):
    """Ubica una dirección. Devuelve (lat, lng, precision).

    precision: 'exacta'     -> se resolvió la dirección completa
               'aproximada' -> cayó al centroide del distrito
               None         -> no se pudo ubicar

    Hace dos intentos porque en Perú OpenStreetMap tiene muchas calles sin
    geocodificar: medido sobre 7 lugares reales, la dirección completa
    acierta 3/7 y el distrito 7/7. El punto aproximado se marca como tal en
    el mapa para que el administrador sepa que debe refinarlo.
    """
    # 1) Dirección completa, la más precisa si responde.
    if direccion:
        partes = [p for p in [direccion, distrito, provincia, departamento] if p]
        consulta = ", ".join(dict.fromkeys(partes))
        if consulta.strip():
            lat, lng = _consultar_nominatim(consulta)
            if lat is not None:
                return lat, lng, "exacta"

    # 2) Fallback al centroide del distrito.
    partes = [p for p in [distrito, provincia, departamento] if p]
    consulta = ", ".join(dict.fromkeys(partes))
    if consulta.strip():
        lat, lng = _consultar_nominatim(consulta)
        if lat is not None:
            return lat, lng, "aproximada"

    return None, None, None


@app.route("/delivery/mapa")
@login_required
def delivery_mapa():
    """Mapa con los pedidos de delivery y sus puntos de entrega."""
    estado_filter = request.args.get("estado") or ""
    query = Pedido.query.filter(Pedido.tipo_entrega == "delivery")
    if estado_filter:
        query = query.filter(Pedido.estado == estado_filter)
    pedidos = query.order_by(Pedido.fecha_pedido.desc()).all()

    puntos = []
    sin_ubicar = 0
    for p in pedidos:
        cliente = Cliente.query.get(p.cliente_id) if p.cliente_id else None
        ubicado = p.lat is not None and p.lng is not None
        if not ubicado:
            sin_ubicar += 1
        puntos.append({
            "id": p.id,
            "estado": p.estado,
            "fecha": p.fecha_pedido,
            "total": float(p.total) if p.total else 0,
            "direccion": p.direccion_entrega or "",
            "cliente": f"{cliente.nombres or ''} {cliente.apellidos or ''}".strip()
                       if cliente else "Cliente eliminado",
            "telefono": cliente.telefono if cliente else None,
            "lat": float(p.lat) if p.lat is not None else None,
            "lng": float(p.lng) if p.lng is not None else None,
            "ubicado": ubicado,
            "precision": p.geo_precision,
        })

    # Punto de la librería, configurable desde el entorno.
    lat_tienda = os.environ.get("MAPA_TIENDA_LAT")
    lng_tienda = os.environ.get("MAPA_TIENDA_LNG")
    tienda = None
    if lat_tienda and lng_tienda and _coordenadas_validas(lat_tienda, lng_tienda):
        tienda = {"lat": float(lat_tienda), "lng": float(lng_tienda),
                  "nombre": os.environ.get("MAPA_TIENDA_NOMBRE", "Librería Salesiana")}

    return render_template("delivery_mapa.html",
                           puntos=puntos,
                           tienda=tienda,
                           sin_ubicar=sin_ubicar,
                           estado_filter=estado_filter)


@app.route("/delivery/mapa/<int:pedido_id>/ubicar", methods=["POST"])
@login_required
@admin_required
@csrf_protect
def delivery_ubicar(pedido_id):
    """El administrador fija a mano el punto de un pedido que no se pudo ubicar."""
    pedido = Pedido.query.get_or_404(pedido_id)
    lat = request.form.get("lat")
    lng = request.form.get("lng")

    if not _coordenadas_validas(lat, lng):
        flash("❌ Coordenadas inválidas o fuera del rango del Perú", "danger")
        return redirect(url_for("delivery_mapa"))

    pedido.lat = float(lat)
    pedido.lng = float(lng)
    pedido.geo_precision = "manual"
    db.session.commit()
    registrar_auditoria("UBICAR_DELIVERY", "pedidos",
                        f"Pedido #{pedido_id} ubicado a mano en {lat}, {lng}")
    flash(f"✅ Pedido #{pedido_id} ubicado en el mapa", "success")
    return redirect(url_for("delivery_mapa"))


@app.route("/pedidos/detalle/<int:pedido_id>")
@login_required
def detalle_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    detalles = db.session.query(DetallePedido, Producto.nombre.label("producto_nombre")).join(Producto).filter(DetallePedido.pedido_id == pedido_id).all()
    cliente = Cliente.query.get(pedido.cliente_id)
    # Buscar venta asociada (opcional, solo si existe)
    venta = Venta.query.filter_by(pedido_id=pedido_id).first()
    es_admin = session.get("rol") == "administrador"
    
    return render_template("pedido_detalle.html", 
                          pedido=pedido, 
                          detalles=detalles, 
                          cliente=cliente,  # ← PASAR EL CLIENTE
                          venta=venta,      # ← PASAR LA VENTA (opcional)
                          es_admin=es_admin)
@app.route("/pedidos/cambiar-estado/<int:pedido_id>", methods=["POST"])
@login_required
def cambiar_estado_pedido(pedido_id):
    # Verificar si es una petición AJAX
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if session.get("rol") != "administrador":
        if is_ajax:
            return jsonify({"success": False, "error": "No autorizado"}), 403
        flash("❌ Solo administradores pueden cambiar estados", "danger")
        return redirect(url_for("ver_pedidos"))
    
    pedido = Pedido.query.get_or_404(pedido_id)
    nuevo_estado = request.form.get("estado")
    
    # Estados válidos
    estados_validos = [
        "pendiente", 
        "confirmado", 
        "preparando", 
        "enviado", 
        "entregado", 
        "listo_tienda", 
        "recogido", 
        "cancelado"
    ]
    
    # Mensajes descriptivos
    mensajes = {
        "pendiente": "⏳ Pedido marcado como pendiente",
        "confirmado": "✅ Pedido confirmado",
        "preparando": "📦 Pedido en preparación",
        "enviado": "🚚 Pedido enviado a domicilio",
        "entregado": "🎁 Pedido entregado al cliente",
        "listo_tienda": "🏪 Pedido listo para recoger en tienda",
        "recogido": "🙌 Cliente recogió su pedido",
        "cancelado": "❌ Pedido cancelado"
    }
    
    if nuevo_estado in estados_validos:
        # Confirmación de entrega: al marcar "entregado" en un delivery se pide quién recibió
        if nuevo_estado == "entregado" and pedido.tipo_entrega == "delivery":
            nombre_recibe = (request.form.get("nombre_recibe") or "").strip()
            if not nombre_recibe:
                mensaje_error = "Para confirmar la entrega, ingresa el nombre de quien recibió el pedido."
                if is_ajax:
                    return jsonify({"success": False, "error": mensaje_error}), 400
                flash(f"❌ {mensaje_error}", "danger")
                return redirect(url_for("ver_pedidos"))
            pedido.nombre_recibe = nombre_recibe
            pedido.dni_recibe = (request.form.get("dni_recibe") or "").strip() or None
            pedido.fecha_entrega = datetime.now()
            pedido.confirmado_por = session.get("nombre") or session.get("usuario_nombre") or "Administrador"

        # Guardar el cambio
        pedido.estado = nuevo_estado
        db.session.commit()
        
        mensaje = mensajes.get(nuevo_estado, f"✅ Pedido #{pedido_id} actualizado a: {nuevo_estado}")
        
        # Al entregar un delivery: correo al cliente con solicitud de confirmación de recepción
        # (se envía antes de responder, tanto en AJAX como en navegación normal)
        if nuevo_estado == "entregado" and pedido.tipo_entrega == "delivery":
            try:
                cliente = Cliente.query.get(pedido.cliente_id)
                if cliente and cliente.correo:
                    enviar_entrega_email(cliente, pedido)
            except Exception as e:
                print(f"Error enviando correo de entrega: {e}")
        
        # Si es AJAX, devolver JSON
        if is_ajax:
            return jsonify({
                "success": True,
                "message": mensaje,
                "estado": nuevo_estado,
                "pedido_id": pedido_id
            })
        
        # Si es normal, mostrar flash
        flash(mensaje, "success")
            
    else:
        if is_ajax:
            return jsonify({"success": False, "error": f"Estado '{nuevo_estado}' no es válido"}), 400
        flash(f"❌ Estado '{nuevo_estado}' no es válido", "danger")
    
    return redirect(url_for("ver_pedidos"))

# ===============================
# API PARA CLIENTES
# ===============================

@app.route("/usuarios-sistema")
@login_required
@permiso_requerido("gestionar_usuarios")
def usuarios_sistema():
    """Panel de gestión de usuarios del sistema con bloqueo/desbloqueo"""
    
    try:
        # ============================================
        # OBTENER TODOS LOS USUARIOS DEL SISTEMA
        # ============================================
        usuarios = db.session.execute(text("""
            SELECT 
                u.id,
                u.correo,
                u.nombres,
                u.apellidos,
                u.rol,
                u.estado,
                u.documento,
                b.id AS bloqueo_id,
                b.motivo AS bloqueo_motivo,
                b.fecha_bloqueo AS bloqueo_fecha,
                b.bloqueado_por AS bloqueo_por,
                CONCAT(bloq.nombres, ' ', bloq.apellidos) AS bloqueo_por_nombre
            FROM usuarios_sistema u
            LEFT JOIN bloqueos b ON u.id = b.usuario_sistema_id 
                AND b.tipo_usuario = 'sistema' 
                AND b.estado = 1
            LEFT JOIN usuarios_sistema bloq ON b.bloqueado_por = bloq.id
            ORDER BY u.id ASC
        """)).mappings().all()
        
        # ============================================
        # VERIFICAR BLOQUEOS AUTOMÁTICOS (intentos_login)
        # ============================================
        intentos_bloqueados = db.session.execute(text("""
            SELECT 
                i.email,
                i.intentos,
                i.email_bloqueado,
                u.id AS usuario_id
            FROM intentos_login i
            JOIN usuarios_sistema u ON i.email = u.correo
            WHERE i.email_bloqueado IS NOT NULL AND i.email_bloqueado > NOW()
        """)).mappings().all()
        
        # Crear un diccionario para verificar bloqueos automáticos
        bloqueos_automaticos = {i['usuario_id']: i for i in intentos_bloqueados}
        
        # ============================================
        # PROCESAR DATOS PARA LA VISTA
        # ============================================
        usuarios_lista = []
        for u in usuarios:
            usuario_dict = dict(u)
            
            # Verificar si tiene bloqueo automático
            if u['id'] in bloqueos_automaticos:
                auto = bloqueos_automaticos[u['id']]
                usuario_dict['bloqueo_automatico'] = True
                usuario_dict['bloqueo_automatico_motivo'] = f"Bloqueo automático por {auto['intentos']} intentos fallidos"
                usuario_dict['bloqueo_automatico_fecha'] = auto['email_bloqueado']
                usuario_dict['bloqueo_automatico_id'] = auto['email']
            else:
                usuario_dict['bloqueo_automatico'] = False
            
            # Estado del usuario
            if usuario_dict['bloqueo_id']:
                usuario_dict['estado_texto'] = '🔒 Bloqueado'
                usuario_dict['estado_badge'] = 'danger'
                usuario_dict['bloqueado'] = True
            elif usuario_dict['bloqueo_automatico']:
                usuario_dict['estado_texto'] = '🔒 Bloqueado (Auto)'
                usuario_dict['estado_badge'] = 'warning'
                usuario_dict['bloqueado'] = True
            else:
                usuario_dict['estado_texto'] = '✅ Activo'
                usuario_dict['estado_badge'] = 'success'
                usuario_dict['bloqueado'] = False
            
            usuarios_lista.append(usuario_dict)
        
        return render_template("usuarios_sistema_gestion.html", usuarios=usuarios_lista)
        
    except Exception as e:
        print(f"❌ Error en usuarios_sistema: {e}")
        flash(f"Error al cargar usuarios: {e}", "danger")
        return render_template("usuarios_sistema_gestion.html", usuarios=[])

@app.route("/api/cliente/direccion")
@login_required_cliente
def api_cliente_direccion():
    try:
        cliente_id = session.get("cliente_id")
        if not cliente_id:
            return jsonify({"success": False, "direccion": "", "error": "No session"})

        cliente = _obtener_cliente_por_id(cliente_id)
        if not cliente:
            return jsonify({"success": False, "direccion": "", "error": "Cliente no encontrado"})

        direccion = cliente.direccion or ""
        return jsonify({"success": True, "direccion": direccion})
    except Exception as e:
        return jsonify({"success": False, "direccion": "", "error": str(e)})

def _api_token():
    """Devuelve el token de APIsPERU desde .env o None."""
    return os.environ.get("API_PERU_TOKEN", "").strip() or None


def consultar_dni_reniec(dni):
    """Consulta un DNI en la API externa de RENIEC (apisperu.com).
    Requiere API_PERU_TOKEN en .env. Devuelve dict con nombres/apellidos o None."""
    token = _api_token()
    if not token:
        return None
    base = os.environ.get("DNI_API_URL", "https://dniruc.apisperu.com/api/v1/dni").strip()
    url = f"{base.rstrip('/')}/{dni}?token={token}"
    req = Request(url, method="GET")
    req.add_header("Accept", "application/json")
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if not data.get("success"):
        return None
    nombres = (data.get("nombres") or "").strip()
    apellido_paterno = (data.get("apellidoPaterno") or "").strip()
    apellido_materno = (data.get("apellidoMaterno") or "").strip()
    apellidos = f"{apellido_paterno} {apellido_materno}".strip()
    if not nombres:
        return None
    return {"nombres": nombres, "apellidos": apellidos}


def consultar_ruc_sunat(ruc):
    """Consulta un RUC en la API externa de SUNAT (apisperu.com).
    Requiere API_PERU_TOKEN en .env. Devuelve dict con razón social/dirección o None."""
    token = _api_token()
    if not token:
        return None
    base = os.environ.get("RUC_API_URL", "https://dniruc.apisperu.com/api/v1/ruc").strip()
    url = f"{base.rstrip('/')}/{ruc}?token={token}"
    req = Request(url, method="GET")
    req.add_header("Accept", "application/json")
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    # La respuesta de RUC viene plana: si no existe devuelve success=false
    if data.get("success") is False:
        return None
    razon_social = (data.get("razonSocial") or "").strip()
    if not razon_social:
        return None
    direccion = (data.get("direccion") or "").strip()
    return {"razon_social": razon_social, "direccion": direccion}


@app.route("/api/admin/consultar-dni/<dni>")
@login_required
def api_consultar_dni_admin(dni):
    """Para registro de usuarios sistema: consulta DNI primero en usuarios_sistema, luego ApiPeru RENIEC.
    Tipo de documento primero -> autocompleta nombres y bloquea edición si encuentra."""
    if session.get("rol") != "administrador":
        return jsonify({"success": False, "error": "Solo administradores"}), 403
    if not dni.isdigit() or len(dni) != 8:
        return jsonify({"success": False, "error": "DNI inválido"}), 400
    # Busca si ya existe como usuario sistema
    existente = UsuarioSistema.query.filter_by(documento=dni).first()
    if existente:
        return jsonify({"success": True, "nombres": existente.nombres, "apellidos": existente.apellidos, "dni": dni, "origen": "bd"})
    info = consultar_dni_reniec(dni)
    if info:
        return jsonify({"success": True, "nombres": info["nombres"], "apellidos": info["apellidos"], "dni": dni, "origen": "reniec"})
    return jsonify({"success": False, "error": "DNI no encontrado en RENIEC"}), 404

@app.route("/api/consultar-dni/<dni>")
@login_required_cliente
def api_consultar_dni_cliente(dni):
    if not dni.isdigit() or len(dni) != 8:
        return jsonify({"success": False, "error": "DNI inválido"}), 400
    
    cliente = None
    try:
        engine = db.get_engine(bind="clientes")
        cliente = db.session.execute(
            text("SELECT dni, nombres, apellidos FROM clientes WHERE dni=:d"),
            {"d": dni}, bind_arguments={"bind": engine}
        ).mappings().first()
    except Exception:
        cliente = None
    if not cliente:
        cli = Cliente.query.filter_by(dni=dni).first()
        if cli:
            cliente = {"dni": cli.dni, "nombres": cli.nombres, "apellidos": cli.apellidos}
    if cliente:
        return jsonify({
            "success": True,
            "nombres": cliente["nombres"],
            "apellidos": cliente["apellidos"],
            "dni": cliente["dni"],
        })
    
    # Si no está en la base interna, consultar RENIEC (si hay token configurado)
    info = consultar_dni_reniec(dni)
    if info:
        # Guardar el DNI en el perfil del cliente logueado (recomendación)
        cid = session.get("cliente_id")
        act = _obtener_cliente_por_id(cid)
        campos = {}
        if act is not None and not act.dni:
            campos["dni"] = dni
            if not act.nombres and info["nombres"]:
                campos["nombres"] = info["nombres"]
            if not act.apellidos and info["apellidos"]:
                campos["apellidos"] = info["apellidos"]
        if campos:
            _guardar_datos_cliente(cid, campos)
        return jsonify({
            "success": True,
            "nombres": info["nombres"],
            "apellidos": info["apellidos"],
            "dni": dni,
        })
    
    return jsonify({"success": False, "error": "DNI no encontrado"}), 404

@app.route("/api/public/consultar-dni/<dni>")
def api_consultar_dni_public(dni):
    """Público para registro cliente: consulta reniec sin login."""
    if not dni.isdigit() or len(dni) != 8:
        return jsonify({"success": False, "error": "DNI inválido"}), 400
    # Busca en clientes existentes (para evitar duplicado, informativo)
    existente = None
    try:
        try:
            eng = db.get_engine(bind="clientes")
        except Exception:
            eng = db.engines.get("clientes") if hasattr(db, "engines") else None
        if eng is not None:
            existente = db.session.execute(text("SELECT nombres, apellidos FROM clientes WHERE dni=:d"), {"d": dni}, bind_arguments={"bind": eng}).mappings().first()
    except Exception:
        pass
    if existente:
        return jsonify({"success": True, "nombres": existente["nombres"], "apellidos": existente["apellidos"], "dni": dni, "origen": "bd"})
    info = consultar_dni_reniec(dni)
    if info:
        return jsonify({"success": True, "nombres": info["nombres"], "apellidos": info["apellidos"], "dni": dni, "origen": "reniec"})
    return jsonify({"success": False, "error": "DNI no encontrado en RENIEC"}), 404

@app.route("/api/consultar-ruc/<ruc>")
@login_required_cliente
def api_consultar_ruc_cliente(ruc):
    if not ruc.isdigit() or len(ruc) != 11:
        return jsonify({"success": False, "error": "RUC inválido"}), 400
    
    # Primero buscar en tabla de empresas
    empresa = RucEmpresa.query.filter_by(ruc=ruc).first()
    if empresa:
        return jsonify({
            "success": True,
            "razon_social": empresa.razon_social,
            "direccion": empresa.direccion or "",
            "ruc": ruc,
        })
    
    # Si no está en la base interna, consultar SUNAT (si hay token configurado)
    info = consultar_ruc_sunat(ruc)
    if info:
        # Guardar el RUC en el perfil del cliente logueado (recomendación)
        cid = session.get("cliente_id")
        act = _obtener_cliente_por_id(cid)
        if act is not None and not getattr(act, "ruc", None):
            _guardar_datos_cliente(cid, {"ruc": ruc})
        return jsonify({
            "success": True,
            "razon_social": info["razon_social"],
            "direccion": info["direccion"],
            "ruc": ruc,
        })
    
    return jsonify({"success": False, "error": "RUC no encontrado"}), 404

# ===============================
# PÁGINAS ESTÁTICAS
# ===============================

@app.route("/acerca-de")
def acerca_de():
    return render_template("acerca_de.html")

@app.route("/contacto")
def contacto():
    return render_template("contacto.html")

# ===============================
# INICIALIZAR BASE DE DATOS
# ===============================

if os.environ.get("AUTO_CREATE_SCHEMA", "false").lower() == "true":
    with app.app_context():
        db.create_all()
        try:
            result = db.session.execute(
                text("SHOW COLUMNS FROM intentos_login LIKE 'email_bloqueado'")
            )
            if not result.fetchone():
                db.session.execute(
                    text("ALTER TABLE intentos_login ADD COLUMN email_bloqueado DATETIME NULL")
                )
                db.session.commit()
                print("Columna email_bloqueado agregada")
        except Exception as e:
            print(f"Migración omitida: {e}")
            db.session.rollback()
        try:
            migraciones_pedidos = {
                "nombre_recibe": "VARCHAR(200) NULL",
                "dni_recibe": "VARCHAR(20) NULL",
                "fecha_entrega": "DATETIME NULL",
                "confirmado_por": "VARCHAR(100) NULL",
                "cliente_confirmo": "INT DEFAULT 0",
                "fecha_confirmacion_cliente": "DATETIME NULL",
            }
            for col, tipo in migraciones_pedidos.items():
                resultado = db.session.execute(
                    text(f"SHOW COLUMNS FROM pedidos LIKE '{col}'")
                )
                if not resultado.fetchone():
                    db.session.execute(text(f"ALTER TABLE pedidos ADD COLUMN {col} {tipo}"))
                    print(f"Columna {col} agregada a pedidos")
            db.session.commit()
        except Exception as e:
            print(f"Migración pedidos omitida: {e}")
            db.session.rollback()
        try:
            migraciones_docs = {
                "clientes": [("ce", "VARCHAR(9) NULL")],
                "ventas": [("cliente_tipo_documento", "VARCHAR(30) NULL")],
            }
            for tabla, columnas in migraciones_docs.items():
                for col, tipo in columnas:
                    resultado = db.session.execute(
                        text(f"SHOW COLUMNS FROM {tabla} LIKE '{col}'")
                    )
                    if not resultado.fetchone():
                        db.session.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}"))
                        print(f"Columna {col} agregada a {tabla}")
            db.session.commit()
        except Exception as e:
            print(f"Migración documentos omitida: {e}")
            db.session.rollback()
        try:
            seed_permisos()
        except Exception as e:
            print(f"Seed permisos omitido: {e}")
            db.session.rollback()

# ===============================
# DASHBOARD
# ===============================

@app.route("/dashboard")
@login_required
@permiso_requerido("ver_dashboard")
def dashboard():
    import pandas as pd
    import plotly
    import plotly.graph_objs as go
    import json
    
    hoy = datetime.now().date()
    inicio_mes = datetime.now().replace(day=1).date()
    hace_30_dias = datetime.now() - timedelta(days=30)
    
    # ========== HORA PERÚ ==========
    ahora_peru = hora_actual_peru()
    
    # ========== 1. ESTADÍSTICAS ==========
    ventas_hoy = Venta.query.filter(func.date(Venta.fecha_venta) == hoy).all()
    total_ventas_hoy = sum(v.cantidad * v.producto.precio for v in ventas_hoy) if ventas_hoy else 0
    cantidad_ventas_hoy = len(ventas_hoy) if ventas_hoy else 0
    
    ventas_mes = Venta.query.filter(func.date(Venta.fecha_venta) >= inicio_mes).all()
    total_ventas_mes = sum(v.cantidad * v.producto.precio for v in ventas_mes) if ventas_mes else 0
    cantidad_ventas_mes = len(ventas_mes) if ventas_mes else 0
    
    pedidos_pendientes = Pedido.query.filter(Pedido.estado == 'pendiente').count()
    pedidos_en_proceso = Pedido.query.filter(Pedido.estado.in_(['confirmado', 'preparando', 'enviado'])).count()
    
    total_clientes = Cliente.query.count()
    hace_7_dias = datetime.now() - timedelta(days=7)
    clientes_nuevos = Cliente.query.filter(Cliente.fecha_registro >= hace_7_dias).count()

    # ========== KPI ADICIONALES ==========
    # Ticket promedio (venta total / nº transacciones)
    ticket_promedio_hoy = (total_ventas_hoy / cantidad_ventas_hoy) if cantidad_ventas_hoy else 0
    ticket_promedio_mes = (total_ventas_mes / cantidad_ventas_mes) if cantidad_ventas_mes else 0

    # Margen bruto (últimos 30 días) usando productos.costo
    margen_res = db.session.execute(
        text("""
            SELECT COALESCE(SUM(v.cantidad * p.precio), 0) AS ingresos,
                   COALESCE(SUM(v.cantidad * COALESCE(p.costo, 0)), 0) AS costo,
                   COUNT(DISTINCT CASE WHEN p.costo IS NOT NULL THEN p.id END) AS con_costo
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            WHERE v.fecha_venta >= :fecha AND v.estado = 1
        """),
        {"fecha": hace_30_dias.date()}
    ).fetchone()
    ingresos_30d = float(margen_res[0] or 0)
    costo_30d = float(margen_res[1] or 0)
    margen_bruto = ingresos_30d - costo_30d
    margen_pct = (margen_bruto / ingresos_30d * 100) if ingresos_30d else 0
    productos_con_costo = int(margen_res[2] or 0)

    # Rotación de inventario (últimos 30 días): unidades vendidas / stock actual
    unidades_vendidas_30d = int(db.session.execute(
        text("""
            SELECT COALESCE(SUM(v.cantidad), 0)
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            WHERE v.fecha_venta >= :fecha AND v.estado = 1
        """),
        {"fecha": hace_30_dias.date()}
    ).scalar() or 0)
    stock_total = int(db.session.execute(
        text("SELECT COALESCE(SUM(cantidad), 0) FROM productos WHERE estado = 1")
    ).scalar() or 0)
    rotacion_inventario = (unidades_vendidas_30d / stock_total) if stock_total else 0
    ventas_diarias = unidades_vendidas_30d / 30
    dias_stock = (stock_total / ventas_diarias) if ventas_diarias else 0

    # Conversión pedido → venta
    total_pedidos = Pedido.query.count()
    pedidos_convertidos = int(db.session.execute(
        text("""
            SELECT COUNT(DISTINCT pedido_id) FROM ventas
            WHERE pedido_id IS NOT NULL AND estado = 1
        """)
    ).scalar() or 0)
    conversion_pedidos = (pedidos_convertidos / total_pedidos * 100) if total_pedidos else 0

    # Ventas por vendedor (últimos 30 días)
    ventas_vendedor = db.session.execute(
        text("""
            SELECT u.id AS vendedor_id,
                   CONCAT(u.nombres, ' ', u.apellidos) AS vendedor,
                   COUNT(*) AS num_ventas,
                   COALESCE(SUM(v.cantidad), 0) AS unidades,
                   COALESCE(SUM(v.cantidad * p.precio), 0) AS total
            FROM ventas v
            JOIN usuarios_sistema u ON u.id = v.vendedor_id
            JOIN productos p ON v.producto_id = p.id
            WHERE v.fecha_venta >= :fecha AND v.estado = 1
            GROUP BY u.id, u.nombres, u.apellidos
            ORDER BY total DESC
        """),
        {"fecha": hace_30_dias.date()}
    ).mappings().all()

    # Desviación de caja (cierres registrados)
    desviacion = db.session.execute(
        text("""
            SELECT COUNT(*) AS total_cierres,
                   COALESCE(SUM(CASE WHEN COALESCE(diferencia, 0) != 0 THEN 1 ELSE 0 END), 0) AS con_diferencia,
                   COALESCE(AVG(ABS(COALESCE(diferencia, 0))), 0) AS promedio_diferencia
            FROM cajas
            WHERE estado = 'cerrada'
        """)
    ).fetchone()
    total_cierres = int(desviacion[0] or 0)
    cierres_con_diferencia = int(desviacion[1] or 0)
    promedio_diferencia = float(desviacion[2] or 0)
    pct_cierres_con_diferencia = (cierres_con_diferencia / total_cierres * 100) if total_cierres else 0

    # Ventas por día
    ventas_por_dia = []
    for i in range(6, -1, -1):
        fecha = datetime.now() - timedelta(days=i)
        fecha_str = fecha.strftime('%d/%m')
        resultado = db.session.execute(
            text("""
                SELECT COALESCE(SUM(v.cantidad * p.precio), 0) as total
                FROM ventas v
                JOIN productos p ON v.producto_id = p.id
                WHERE DATE(v.fecha_venta) = :fecha
            """),
            {"fecha": fecha.date()}
        ).fetchone()
        total_dia = float(resultado[0]) if resultado and resultado[0] else 0
        ventas_por_dia.append({'fecha': fecha_str, 'total': total_dia})
    
    # Top productos - CORREGIDO (SIN IMAGEN)
    top_productos = db.session.query(
        Producto.nombre,
        func.sum(Venta.cantidad).label('total_vendido')
    ).join(Venta).filter(
        func.date(Venta.fecha_venta) >= hace_30_dias.date()
    ).group_by(Producto.id).order_by(func.sum(Venta.cantidad).desc()).limit(5).all()
    
    # Stock (usando umbrales configurables)
    stock_bajo = Producto.query.filter(Producto.cantidad > 0, Producto.cantidad <= Producto.stock_minimo).order_by(Producto.cantidad.asc()).limit(10).all()
    stock_critico = Producto.query.filter(Producto.cantidad == 0).order_by(Producto.nombre.asc()).limit(10).all()
    stock_exceso = Producto.query.filter(Producto.cantidad >= Producto.stock_maximo).order_by(Producto.cantidad.desc()).limit(10).all()
    
    # ========== 2. GRÁFICOS CON PLOTLY ==========
    
    # Gráfico 1: Ventas últimos 7 días
    fechas_7d = [datetime.now() - timedelta(days=i) for i in range(6, -1, -1)]
    ventas_7d = []
    for fecha in fechas_7d:
        resultado = db.session.execute(
            text("""
                SELECT COALESCE(SUM(v.cantidad * p.precio), 0) as total
                FROM ventas v
                JOIN productos p ON v.producto_id = p.id
                WHERE DATE(v.fecha_venta) = :fecha
            """),
            {"fecha": fecha.date()}
        ).fetchone()
        ventas_7d.append(float(resultado[0]) if resultado else 0)
    
    fig_ventas = go.Figure()
    fig_ventas.add_trace(go.Bar(
        x=[fecha.strftime('%d/%m') for fecha in fechas_7d],
        y=ventas_7d,
        name='Ventas (S/)',
        marker_color='#2563eb',
        text=[f'S/. {v:.2f}' for v in ventas_7d],
        textposition='outside'
    ))
    fig_ventas.update_layout(
        title='📈 Ventas Últimos 7 Días',
        xaxis_title='Fecha',
        yaxis_title='Total S/.',
        template='plotly_white',
        height=350,
        showlegend=False
    )
    
    # Gráfico 2: Top productos
    fig_top = go.Figure()
    if top_productos:
        nombres = [p[0] for p in top_productos]   
        vendidos = [float(p[1]) for p in top_productos] 
        fig_top.add_trace(go.Bar(
            x=nombres,
            y=vendidos,
            name='Unidades',
            marker_color='#10b981',
            text=vendidos,
            textposition='outside'
        ))
    fig_top.update_layout(
        title='🏆 Top 5 Productos Más Vendidos',
        xaxis_title='Producto',
        yaxis_title='Unidades Vendidas',
        template='plotly_white',
        height=350,
        showlegend=False
    )
    
    # Gráfico 3: Ventas por categoría
    ventas_categoria = db.session.execute(
        text("""
            SELECT c.nombre as categoria,
                   COALESCE(SUM(v.cantidad * p.precio), 0) as total_ventas
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
            WHERE v.fecha_venta >= :fecha_inicio
            GROUP BY c.nombre
            ORDER BY total_ventas DESC
        """),
        {"fecha_inicio": hace_30_dias.date()}
    ).fetchall()
    
    fig_cat = go.Figure()
    if ventas_categoria:
        categorias = [row[0] or 'Sin categoría' for row in ventas_categoria]
        totales = [float(row[1]) for row in ventas_categoria]
        fig_cat.add_trace(go.Pie(
            labels=categorias,
            values=totales,
            hole=0.4,
            marker=dict(colors=['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'])
        ))
    fig_cat.update_layout(
        title='📊 Ventas por Categoría',
        template='plotly_white',
        height=350,
        showlegend=True
    )
    
    # Gráfico 4: Estado de pedidos
    estados_pedidos = db.session.execute(
        text("""
            SELECT estado, COUNT(*) as cantidad
            FROM pedidos
            GROUP BY estado
        """)
    ).fetchall()
    
    fig_estados = go.Figure()
    if estados_pedidos:
        estados = [row[0] for row in estados_pedidos]
        cantidades = [row[1] for row in estados_pedidos]
        colores = {'pendiente': '#f59e0b', 'confirmado': '#3b82f6', 
                   'preparando': '#8b5cf6', 'enviado': '#06b6d4',
                   'entregado': '#10b981', 'cancelado': '#ef4444'}
        colors = [colores.get(e, '#6b7280') for e in estados]
        fig_estados.add_trace(go.Bar(
            x=estados,
            y=cantidades,
            marker_color=colors,
            text=cantidades,
            textposition='outside'
        ))
    fig_estados.update_layout(
        title='📋 Estado de Pedidos',
        xaxis_title='Estado',
        yaxis_title='Cantidad',
        template='plotly_white',
        height=350,
        showlegend=False
    )
    
    # ========== 3. CONVERTIR GRÁFICOS A JSON ==========
    graph_ventas = json.dumps(fig_ventas, cls=plotly.utils.PlotlyJSONEncoder)
    graph_top = json.dumps(fig_top, cls=plotly.utils.PlotlyJSONEncoder)
    graph_cat = json.dumps(fig_cat, cls=plotly.utils.PlotlyJSONEncoder)
    graph_estados = json.dumps(fig_estados, cls=plotly.utils.PlotlyJSONEncoder)
    
    # ========== 4. RENDERIZAR TEMPLATE ==========
    return render_template("dashboard.html",
                          total_ventas_hoy=total_ventas_hoy,
                          cantidad_ventas_hoy=cantidad_ventas_hoy,
                          total_ventas_mes=total_ventas_mes,
                          cantidad_ventas_mes=cantidad_ventas_mes,
                          pedidos_pendientes=pedidos_pendientes,
                          pedidos_en_proceso=pedidos_en_proceso,
                          total_clientes=total_clientes,
                          clientes_nuevos=clientes_nuevos,
                          ventas_por_dia=ventas_por_dia,
                          top_productos=top_productos,
                          stock_bajo=stock_bajo,
                          stock_critico=stock_critico,
                          stock_exceso=stock_exceso,
                          graph_ventas=graph_ventas,
                          graph_top=graph_top,
                          graph_cat=graph_cat,
                          graph_estados=graph_estados,
                          ticket_promedio_hoy=ticket_promedio_hoy,
                          ticket_promedio_mes=ticket_promedio_mes,
                          margen_bruto=margen_bruto,
                          margen_pct=margen_pct,
                          productos_con_costo=productos_con_costo,
                          unidades_vendidas_30d=unidades_vendidas_30d,
                          rotacion_inventario=rotacion_inventario,
                          dias_stock=dias_stock,
                          conversion_pedidos=conversion_pedidos,
                          pedidos_convertidos=pedidos_convertidos,
                          total_pedidos=total_pedidos,
                          ventas_vendedor=ventas_vendedor,
                          total_cierres=total_cierres,
                          cierres_con_diferencia=cierres_con_diferencia,
                          pct_cierres_con_diferencia=pct_cierres_con_diferencia,
                          promedio_diferencia=promedio_diferencia,
                          datetime=datetime,
                          timedelta=timedelta,
                          ahora_peru=ahora_peru) 

@app.route("/procesar_pago", methods=["POST"])
@login_required_cliente
def procesar_pago():
    try:
        data = request.get_json()
        
        email_cliente = data.get("email")
        nombres = data.get("nombres")
        apellidos = data.get("apellidos")
        total = data.get("total")
        tipo_comprobante = data.get("tipo_comprobante")
        productos = data.get("productos", [])
        

        html_comprobante = generar_comprobante_pedido(nombres, apellidos, productos, total, tipo_comprobante)
        

        asunto = f"✅ Comprobante de {tipo_comprobante.upper()} - Librería Salesiana"
        exito, msg = enviar_comprobante_email(email_cliente, asunto, html_comprobante)
        
        if exito:
            return jsonify({"success": True, "message": "Correo enviado correctamente"})
        else:
            return jsonify({"success": False, "message": f"Error al enviar: {msg}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

def generar_comprobante_pedido(nombres, apellidos, productos, total, tipo_comprobante):
    cliente_nombre = f"{nombres} {apellidos}".strip()
    productos_html = ""
    for item in productos:
        productos_html += f"""
        <tr>
            <td>{item.get('nombre', 'Producto')}</td>
            <td style="text-align: center">{item.get('cantidad', 1)}</td>
            <td style="text-align: right">S/. {item.get('precio', 0):.2f}</td>
            <td style="text-align: right">S/. {item.get('precio', 0) * item.get('cantidad', 1):.2f}</td>
        </tr>
        """
    
    if tipo_comprobante == "factura":
        titulo = "FACTURA ELECTRÓNICA"
        ruc_html = f"<p><strong>RUC:</strong> {productos[0].get('ruc', '—') if productos else '—'}</p>"
    else:
        titulo = "BOLETA DE VENTA ELECTRÓNICA"
        ruc_html = ""
    
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Comprobante de Venta</title></head>
<body style="font-family: Arial, sans-serif;">
<div style="max-width: 600px; margin: auto; background: #f8f9fa; padding: 20px; border-radius: 10px;">
    <div style="background: #007bff; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
        <h2>📚 LIBRERÍA SALESIANA DON BOSCO</h2>
        <p>{titulo}</p>
    </div>
    <div style="padding: 20px; background: white;">
        <p><strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <p><strong>Cliente:</strong> {cliente_nombre}</p>
        {ruc_html}
        <hr>
        <h4>Detalle de compra:</h4>
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background: #e9ecef;">
                    <th style="padding: 8px; text-align: left;">Producto</th>
                    <th style="padding: 8px; text-align: center;">Cant.</th>
                    <th style="padding: 8px; text-align: right;">Precio</th>
                    <th style="padding: 8px; text-align: right;">Subtotal</th>
                </tr>
            </thead>
            <tbody>
                {productos_html}
            </tbody>
            <tfoot>
                <tr>
                    <td colspan="3" style="text-align: right; padding: 10px;"><strong>TOTAL:</strong></td>
                    <td style="text-align: right; padding: 10px;"><strong>S/. {total:.2f}</strong></td>
                </tr>
            </tfoot>
        </table>
        <hr>
        <p style="text-align: center;">✨ ¡Gracias por su compra! Que Dios lo bendiga. ✨</p>
    </div>
</div>
</body>
</html>"""

@app.route("/mis-pedidos/detalle/<int:pedido_id>")
@login_required_cliente
def cliente_detalle_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    

    if pedido.cliente_id != session.get("cliente_id"):
        flash("❌ No tienes permiso para ver este pedido", "danger")
        return redirect(url_for("mis_pedidos"))
    

    detalles = db.session.query(DetallePedido, Producto.nombre.label("producto_nombre")).join(Producto).filter(DetallePedido.pedido_id == pedido_id).all()
    

    cliente = Cliente.query.get(pedido.cliente_id)
    

    venta = None
    

    venta = Venta.query.filter_by(pedido_id=pedido_id).first()
    

    if not venta and cliente and cliente.dni:
        venta = Venta.query.filter_by(cliente_documento=cliente.dni).order_by(Venta.fecha_venta.desc()).first()
    

    if not venta and cliente and cliente.correo:
        venta = Venta.query.filter_by(cliente_email=cliente.correo).order_by(Venta.fecha_venta.desc()).first()
    

    print("=" * 50)
    print(f"🔍 Pedido #{pedido_id} - Cliente: {cliente.nombres if cliente else 'N/A'}")
    print(f"   Venta encontrada: {venta.id if venta else 'NO'}")
    if venta:
        print(f"   Número comprobante: {venta.numero_comprobante}")
        print(f"   Tipo: {venta.tipo_comprobante}")
        print(f"   Razón Social: {venta.cliente_razon_social}")
        print(f"   Dirección Fiscal: {venta.cliente_direccion_fiscal}")
    print("=" * 50)
    
    return render_template("cliente_pedido_detalle.html", 
                          pedido=pedido, 
                          detalles=detalles, 
                          cliente=cliente, 
                          venta=venta)



# =============================================
# MICROSERVICIOS - Blueprints registrados desde el paquete www/microservicios
# (comercial -> /api/comercial, inventario -> /api/inventario, monitor -> /api/health)
# =============================================

@app.route("/microservicios/dashboard")
@login_required
def microservicios_dashboard():
    """Dashboard para monitorear microservicios - producción real: lee directo de las BDs dueñas (binds),
    no de los espejos librospe_db.comercial_*/inventario_* que serán eliminados."""
    if session.get("rol") != "administrador":
        flash("❌ Solo administradores pueden ver este panel", "danger")
        return redirect(url_for("dashboard"))

    # Motores de microservicios (dueños de datos) - no librospe_db
    try:
        engine_ventas = db.get_engine(bind="ventas")
    except Exception:
        engine_ventas = db.engines.get("ventas") if hasattr(db, "engines") else None
    try:
        engine_inventario = db.get_engine(bind="inventario")
    except Exception:
        engine_inventario = db.engines.get("inventario") if hasattr(db, "engines") else None

    def _count(sql, engine):
        try:
            return db.session.execute(text(sql), bind_arguments={"bind": engine}).scalar() or 0
        except Exception:
            # Fallback temporal mientras se eliminan espejos: intenta librospe_db
            try:
                return db.session.execute(text(sql)).scalar() or 0
            except Exception:
                return 0

    total_pedidos = _count("SELECT COUNT(*) FROM comercial_pedidos", engine_ventas)
    pedidos_pendientes = _count("SELECT COUNT(*) FROM comercial_pedidos WHERE estado = 'pendiente'", engine_ventas)
    pedidos_confirmados = _count("SELECT COUNT(*) FROM comercial_pedidos WHERE estado = 'confirmado'", engine_ventas)
    total_productos = _count("SELECT COUNT(*) FROM inventario_productos", engine_inventario)
    productos_bajo_stock = _count("SELECT COUNT(*) FROM inventario_productos WHERE cantidad < 10", engine_inventario)
    productos_agotados = _count("SELECT COUNT(*) FROM inventario_productos WHERE cantidad = 0", engine_inventario)
    
    return render_template("microservicios_dashboard.html",
                          total_pedidos=total_pedidos,
                          pedidos_pendientes=pedidos_pendientes,
                          pedidos_confirmados=pedidos_confirmados,
                          total_productos=total_productos,
                          productos_bajo_stock=productos_bajo_stock,
                          productos_agotados=productos_agotados)

# =============================================
# ADMIN CLIENTES - Gestión real desde microservicio (dueño librospe_ms_clientes)
# =============================================
@app.route("/admin/clientes")
@login_required
def admin_clientes():
    if session.get("rol") != "administrador":
        flash("❌ Solo administradores", "danger")
        return redirect(url_for("dashboard"))
    try:
        engine = db.get_engine(bind="clientes")
    except Exception:
        engine = db.engines.get("clientes") if hasattr(db, "engines") else None
    try:
        clientes = db.session.execute(text(
            "SELECT id, nombres, apellidos, correo, telefono, dni, ce, departamento, provincia, distrito, estado FROM clientes ORDER BY id DESC"
        ), bind_arguments={"bind": engine}).mappings().all()
    except Exception as e:
        flash(f"❌ Error al listar clientes del microservicio: {e}", "danger")
        clientes = []
    return render_template("admin_clientes.html", clientes=clientes)

@app.route("/admin/clientes/<int:cid>/editar", methods=["POST"])
@login_required
def admin_clientes_editar(cid):
    if session.get("rol") != "administrador":
        flash("❌ Solo administradores", "danger")
        return redirect(url_for("dashboard"))
    try:
        engine = db.get_engine(bind="clientes")
    except Exception:
        engine = db.engines.get("clientes") if hasattr(db, "engines") else None
    # Soporta tanto modal nuevo (tipo_documento+numero_documento) como legacy (dni/ce)
    tipo = (request.form.get("tipo_documento") or "").strip().upper()
    numero = (request.form.get("numero_documento") or "").strip() or None
    if tipo:
        dni_val = numero if tipo == "DNI" else None
        ce_val = numero if tipo == "CE" else None
    else:
        dni_val = (request.form.get("dni") or "").strip() or None
        ce_val = (request.form.get("ce") or "").strip() or None
    data = {
        "nombres": (request.form.get("nombres") or "").strip() or None,
        "apellidos": (request.form.get("apellidos") or "").strip() or None,
        "correo": (request.form.get("correo") or "").strip() or None,
        "telefono": armar_telefono(request.form.get("prefijo"), request.form.get("telefono")),
        "dni": dni_val, "ce": ce_val
    }
    # Verifica duplicado correo en microservicio
    if data.get("correo"):
        dup = db.session.execute(text("SELECT id FROM clientes WHERE correo=:c AND id!=:id"),
            {"c": data["correo"], "id": cid}, bind_arguments={"bind": engine}).scalar()
        if dup:
            flash("❌ Correo ya registrado por otro cliente", "danger")
            return redirect(url_for("admin_clientes"))
    try:
        db.session.execute(text("""
            UPDATE clientes SET nombres=:nombres, apellidos=:apellidos, correo=:correo,
                telefono=:telefono, dni=:dni, ce=:ce WHERE id=:id
        """), {**data, "id": cid}, bind_arguments={"bind": engine})
        db.session.commit()
        flash("✅ Cliente actualizado (microservicio)", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {e}", "danger")
    return redirect(url_for("admin_clientes"))

@app.route("/admin/clientes/<int:cid>/eliminar", methods=["POST"])
@login_required
def admin_clientes_eliminar(cid):
    if session.get("rol") != "administrador":
        flash("❌ Solo administradores", "danger")
        return redirect(url_for("dashboard"))
    try:
        engine = db.get_engine(bind="clientes")
    except Exception:
        engine = db.engines.get("clientes") if hasattr(db, "engines") else None
    try:
        db.session.execute(text("UPDATE clientes SET estado=0 WHERE id=:id"), {"id": cid}, bind_arguments={"bind": engine})
        db.session.commit()
        flash("✅ Cliente desactivado (estado=0)", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {e}", "danger")
    return redirect(url_for("admin_clientes"))

@app.route("/admin/clientes/<int:cid>/activar", methods=["POST"])
@login_required
def admin_clientes_activar(cid):
    if session.get("rol") != "administrador":
        flash("❌ Solo administradores", "danger")
        return redirect(url_for("dashboard"))
    try:
        engine = db.get_engine(bind="clientes")
    except Exception:
        engine = db.engines.get("clientes") if hasattr(db, "engines") else None
    try:
        db.session.execute(text("UPDATE clientes SET estado=1 WHERE id=:id"), {"id": cid}, bind_arguments={"bind": engine})
        db.session.commit()
        flash("✅ Cliente activado", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {e}", "danger")
    return redirect(url_for("admin_clientes"))


# =============================================
# REGISTRO DE MICROSERVICIOS
# Los blueprints (comercial, inventario y monitor) viven en el paquete
# independiente www/microservicios. Aqui se inyectan las dependencias
# compartidas (db y login_required).
# =============================================
register_microservicios(app, db, login_required)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
application = app
