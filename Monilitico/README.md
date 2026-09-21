# LibrosPE - MONOLITO

Versión monolítica pura: **1 app Flask + 1 base de datos propia (`librospe_monolito`)**,
separada de las 5 BDs de microservicios.

## Estructura

- `www/app.py` (~5490 líneas, 90 rutas, sin `microservicios/` ni binds)
- `www/templates/` + `www/static/` (interfaz completa)
- `BD_Monolito.sql` (schema único `librospe_monolito`: 17 tablas + 1 vista,
  sin `comercial_*` ni `inventario_*`)
- `.env` solo necesita `DB_NAME=librospe_monolito` (sin `MS_*` ni `SERVICE_TOKEN`)

## Crear la BD

```sql
SOURCE BD_Monolito.sql;
```

## Arranque local

```bat
run_local.bat
```

Abrir http://localhost:8000

## Diferencia con microservicios

Ver `../Micrososervicios/README_MICROSERVICIOS.md`: 1 gateway (puerto 8000) + 4 servicios
independientes (inventario 8001, ventas 8002, usuarios 8003, clientes 8004),
cada uno con su propia BD y comunicación HTTP + `X-Service-Token`.
