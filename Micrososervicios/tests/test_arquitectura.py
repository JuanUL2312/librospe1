"""Pruebas de la arquitectura de microservicios.

Comprueba que:
- Cada modelo tiene su bind (microservicio dueno) y ninguna tabla queda
  en la base central.
- El SQL crudo se enruta al microservicio correcto.
- Los modelos espejo (copias locales de claves foraneas) estan declarados.
- El script de sincronizacion cubre todas las copias.
"""
import ast
import pathlib
import re

import pytest

WWW = pathlib.Path(__file__).resolve().parent.parent / "www"
RAIZ = WWW.parent

BIND_POR_MODELO = {
    "Producto": "inventario", "Categoria": "inventario", "Proveedor": "inventario",
    "ConteoStock": "inventario",
    "Venta": "ventas", "Pedido": "ventas", "DetallePedido": "ventas", "Caja": "ventas",
    "UsuarioSistema": "usuarios", "Rol": "usuarios", "Permiso": "usuarios",
    "RolPermiso": "usuarios", "Bloqueo": "usuarios", "IntentosLogin": "usuarios",
    "Auditoria": "usuarios",
    "Cliente": "clientes", "RucEmpresa": "clientes", "Departamento": "clientes",
    "Provincia": "clientes", "Distrito": "clientes",
}


def _modelos():
    """(clase, tabla, bind) de cada modelo de app.py (analisis estatico)."""
    src = (WWW / "app.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(src)
    salida = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any("Model" in ast.unparse(b) for b in node.bases):
            continue
        tabla = bind = None
        for item in node.body:
            if isinstance(item, ast.Assign):
                if isinstance(item.value, ast.Constant):
                    nombre = [ast.unparse(t) for t in item.targets]
                    if nombre == ["__tablename__"]:
                        tabla = item.value.value
                    if nombre == ["__bind_key__"]:
                        bind = item.value.value
        if tabla:
            salida.append((node.name, tabla, bind))
    return salida


def test_todo_modelo_tiene_su_microservicio():
    """Ningun modelo puede quedarse en la base central."""
    sin_bind = [c for c, t, b in _modelos() if not b]
    assert not sin_bind, f"modelos sin __bind_key__: {sin_bind}"


def test_bind_correcto_de_cada_modelo():
    for clase, tabla, bind in _modelos():
        if clase in BIND_POR_MODELO:
            assert bind == BIND_POR_MODELO[clase], f"{clase} deberia estar en {BIND_POR_MODELO[clase]}"


def test_modelos_espejo_declarados():
    """Las copias locales de claves foraneas deben existir."""
    nombres = {c for c, t, b in _modelos()}
    for espejo in ("ProductoEnVentas", "UsuarioEnVentas",
                   "VentaEnInventario", "UsuarioEnInventario"):
        assert espejo in nombres, f"falta el modelo espejo {espejo}"


def test_enrutado_de_sql_crudo():
    """El SQL crudo se enruta segun las tablas que menciona."""
    from app import _servicio_de_sql
    assert _servicio_de_sql("SELECT * FROM ventas WHERE id=1") == "ventas"
    assert _servicio_de_sql("SELECT * FROM productos p JOIN categorias c") == "inventario"
    assert _servicio_de_sql("SELECT * FROM usuarios_sistema") == "usuarios"
    assert _servicio_de_sql("SELECT * FROM clientes") == "clientes"
    # tablas de varios servicios -> ambiguo (se avisa y se usa el default)
    assert _servicio_de_sql("SELECT * FROM ventas v JOIN clientes c") is None


def test_sincronizacion_cubre_las_copias():
    """El script de sincronizacion debe reflejar cada copia local."""
    sql = (RAIZ / "sincronizar_copias.sql").read_text(encoding="utf-8")
    assert (WWW / "sincronizar_copias.sql").read_text(encoding="utf-8") == sql
    for destino, origen in [
        ("librospe_ms_ventas.proveedores", "librospe_ms_inventario.proveedores"),
        ("librospe_ms_inventario.ventas", "librospe_ms_ventas.ventas"),
    ]:
        bd_dest, tabla_dest = destino.split(".")
        bd_ori, tabla_ori = origen.split(".")
        assert f"`{bd_dest}`.`{tabla_dest}`" in sql, f"falta la copia hacia {destino}"
        assert f"`{bd_ori}`.`{tabla_ori}`" in sql, f"falta el origen {origen}"
    assert "`librospe_ms_ventas`.`clientes`" not in sql
    assert "`librospe_ms_ventas`.`productos`" not in sql
    assert "`librospe_ms_ventas`.`categorias`" not in sql
    assert "`librospe_ms_ventas`.`usuarios_sistema`" not in sql
    assert "`librospe_ms_ventas`.`roles`" not in sql
    vista = (RAIZ / "migracion_productos_fuente_unica.sql").read_text(encoding="utf-8")
    assert "FROM librospe_ms_inventario.inventario_productos" in vista


def test_lista_pedidos_no_une_clientes_de_otra_base():
    """La pantalla de pedidos resuelve clientes con su bind propietario."""
    codigo = (WWW / "app.py").read_text(encoding="utf-8-sig")
    inicio = codigo.index("def ver_pedidos():")
    fin = codigo.index("# ========================================================================", inicio)
    ruta = codigo[inicio:fin]
    assert "ClienteEnVentas" not in ruta
    assert "Cliente.query" in ruta
    assert "Pedido.cliente_id.in_(ids_clientes_busqueda)" in ruta


def test_reporte_ubicacion_no_consulta_tabla_espejo_de_clientes():
    codigo = (WWW / "app.py").read_text(encoding="utf-8-sig")
    inicio = codigo.index("def _listar_ubicaciones_distrito_clientes():")
    fin = codigo.index("@app.route(\"/reportes/ventas_por_ubicacion\"", inicio)
    reporte = codigo[inicio:fin]
    assert "ClienteEnVentas" not in reporte
    assert "LEFT JOIN clientes" not in reporte
    assert "Cliente.query" in reporte


def test_no_se_consulta_librospe_db():
    """Ninguna consulta SQL puede apuntar a la base central (eliminada)."""
    codigo = (WWW / "app.py").read_text(encoding="utf-8-sig")
    patrones = ("FROM librospe_db", "JOIN librospe_db", "INTO librospe_db",
                "UPDATE librospe_db")
    for patron in patrones:
        assert patron not in codigo, f"el codigo consulta la base central: {patron}"


def test_puerto_opcional_en_la_uri():
    """DB_PORT debe poder sobreescribir el 3306 (entornos de prueba)."""
    src = (WWW / "app.py").read_text(encoding="utf-8-sig")
    assert "DB_PORT" in src
