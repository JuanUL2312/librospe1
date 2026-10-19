"""Migracion de librospe_db hacia los 4 microservicios.

Reparte las 20 tablas de librospe_db entre las bases de cada microservicio
(la tabla "duena" de cada dominio) y crea/actualiza las COPIAS LOCALES de las
claves foraneas que cada servicio necesita para poder hacer JOIN dentro de su
propia base (MySQL no puede unir tablas de bases distintas).

Uso:
  python migrar_a_microservicios.py --host H --user U --password P [--apply]

Por defecto solo informa (dry-run). Con --apply ejecuta los cambios.
"""
import argparse, os, sys, pathlib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pymysql

# ------------------------------------------------------------------
# 1) Tablas "duenas": cada microservicio es el unico que las escribe
# ------------------------------------------------------------------
DUENAS = {
    "librospe_ms_inventario": [
        "productos", "categorias", "proveedores",
        "conteos_stock", "movimientos_stock",
    ],
    "librospe_ms_ventas": [
        "ventas", "pedidos", "detalle_pedido", "cajas", "movimientos_caja",
        "cupones", "pagos", "ajustes_pago", "resenas", "inventario_diario",
    ],
    "librospe_ms_usuarios": [
        "usuarios_sistema", "roles", "permisos", "rol_permisos",
        "intentos_login", "bloqueos", "auditoria",
        "configuracion_sistema", "cambios_configuracion",
    ],
    "librospe_ms_clientes": [
        "clientes", "ruc_empresas",
        "departamentos", "provincias", "distritos",
    ],
}

# ------------------------------------------------------------------
# 2) Copias locales de claves foraneas (para los JOIN internos)
#    microservicio -> (tablas que necesita replicadas)
#    Cada servicio guarda en su propia base las filas de las claves
#    foraneas que usa, para poder hacer JOIN sin cruzar bases.
# ------------------------------------------------------------------
COPIAS = {
    "librospe_ms_ventas": {
        "productos": "librospe_ms_inventario",
        "categorias": "librospe_ms_inventario",
        "proveedores": "librospe_ms_inventario",
        "usuarios_sistema": "librospe_ms_usuarios",
        "roles": "librospe_ms_usuarios",
        "clientes": "librospe_ms_clientes",
    },
    "librospe_ms_inventario": {
        "usuarios_sistema": "librospe_ms_usuarios",
        "ventas": "librospe_ms_ventas",
    },
}

ORIGEN = "librospe_db"


def conectar(host, user, password, port=3306):
    return pymysql.connect(host=host, user=user, password=password,
                           port=port, charset="utf8mb4", autocommit=False)


def columnas(cur, bd, tabla):
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position""",
                (bd, tabla))
    return [r[0] for r in cur.fetchall()]


def contar(cur, bd, tabla):
    cur.execute(f"SELECT COUNT(*) FROM `{bd}`.`{tabla}`")
    return cur.fetchone()[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("DB_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("DB_PORT", "3306")))
    ap.add_argument("--user", default=os.environ.get("DB_USER", "root"))
    ap.add_argument("--password", default=os.environ.get("DB_PASSWORD", ""))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = conectar(args.host, args.user, args.password, args.port)
    cur = conn.cursor()

    print("=" * 74)
    print("MIGRACION librospe_db -> 4 microservicios", "(APLICANDO)" if args.apply else "(SIMULACION)")
    print("=" * 74)

    # --- A) Tablas dueñas -------------------------------------------------
    for bd, tablas in DUENAS.items():
        print(f"\n### {bd}")
        for tabla in tablas:
            cols_ori = columnas(cur, ORIGEN, tabla)
            if not cols_ori:
                print(f"  - {tabla:26} NO existe en {ORIGEN} -> se omite")
                continue
            n = contar(cur, ORIGEN, tabla)
            cols_dest = columnas(cur, bd, tabla)
            if not cols_dest:
                if args.apply:
                    cur.execute(f"CREATE TABLE `{bd}`.`{tabla}` LIKE `{ORIGEN}`.`{tabla}`")
                    print(f"  + {tabla:26} CREADA (like {ORIGEN})")
                else:
                    print(f"  + {tabla:26} se crearia (like {ORIGEN})")
            else:
                faltan = [c for c in cols_ori if c not in cols_dest]
                extra = [c for c in cols_dest if c not in cols_ori]
                if faltan or extra:
                    print(f"  ! {tabla:26} ESTRUCTURA DISTINTA  faltan={faltan} extra={extra}")
                    continue
                print(f"  = {tabla:26} ya existe (misma estructura)")
            n = contar(cur, ORIGEN, tabla)
            if args.apply:
                # Se desactivan las FK para poder recargar la tabla (hay tablas
                # que la referencian, p.ej. inventario_diario -> productos).
                cur.execute("SET FOREIGN_KEY_CHECKS=0")
                cur.execute(f"DELETE FROM `{bd}`.`{tabla}`")
                cols = ", ".join(f"`{c}`" for c in cols_ori)
                cur.execute(f"INSERT INTO `{bd}`.`{tabla}` ({cols}) "
                            f"SELECT {cols} FROM `{ORIGEN}`.`{tabla}`")
                cur.execute("SET FOREIGN_KEY_CHECKS=1")
                print(f"      -> copiadas {n} filas de {ORIGEN}")
            else:
                print(f"      -> se copiarian {n} filas de {ORIGEN}")

    # --- B) Copias locales ----------------------------------------------
    print("\n\n### COPIAS LOCALES (claves foraneas para JOIN dentro de cada base)")
    for bd, origenes in COPIAS.items():
        print(f"\n### {bd}")
        for tabla, bd_duena in origenes.items():
            cols_duena = columnas(cur, bd_duena, tabla)
            if not cols_duena:
                print(f"  - {tabla:22} (no esta aun en {bd_duena})")
                continue
            cols_dest = columnas(cur, bd, tabla)
            if cols_dest and [c for c in cols_duena if c not in cols_dest]:
                # Es una copia antigua con otra forma: se aparta con el sufijo
                # _legacy (no se borra nada) y se recrea con la del dueno.
                print(f"  ! {tabla:22} estructura distinta -> se aparta como {tabla}_legacy")
                if args.apply:
                    cur.execute("SET FOREIGN_KEY_CHECKS=0")
                    cur.execute(f"DROP TABLE IF EXISTS `{bd}`.`{tabla}_legacy`")
                    cur.execute(f"RENAME TABLE `{bd}`.`{tabla}` TO `{bd}`.`{tabla}_legacy`")
                    cur.execute(f"CREATE TABLE `{bd}`.`{tabla}` LIKE `{bd_duena}`.`{tabla}`")
                    cur.execute("SET FOREIGN_KEY_CHECKS=1")
                cols_dest = []
            if not cols_dest:
                if args.apply:
                    cur.execute(f"CREATE TABLE IF NOT EXISTS `{bd}`.`{tabla}` LIKE `{bd_duena}`.`{tabla}`")
                    print(f"  + {tabla:22} CREADA (like {bd_duena})")
                else:
                    print(f"  + {tabla:22} se crearia (like {bd_duena})")
            else:
                print(f"  = {tabla:22} ya existe (misma estructura)")
            n = contar(cur, bd_duena, tabla)
            if args.apply:
                cur.execute("SET FOREIGN_KEY_CHECKS=0")
                cur.execute(f"DELETE FROM `{bd}`.`{tabla}`")
                cols = ", ".join(f"`{c}`" for c in cols_duena)
                cur.execute(f"INSERT INTO `{bd}`.`{tabla}` ({cols}) "
                            f"SELECT {cols} FROM `{bd_duena}`.`{tabla}`")
                cur.execute("SET FOREIGN_KEY_CHECKS=1")
                print(f"      -> copiadas {n} filas desde {bd_duena}")
            else:
                print(f"      -> se copiarian {n} filas desde {bd_duena}")

    if args.apply:
        conn.commit()
        print("\n✅ Migracion aplicada (commit).")
    else:
        conn.rollback()
        print("\nℹ️  Simulacion: no se aplico nada (usa --apply).")
    conn.close()


if __name__ == "__main__":
    main()
