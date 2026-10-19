# LibrosPE - MICROSERVICIOS

1 gateway + 4 servicios independientes, cada uno con **su propia BD** y
comunicación **HTTP + `X-Service-Token`**. Sin SQL cruzado entre BDs.

> **Nota:** en producción todo corre dentro de un mismo proceso uWSGI
> (`processes = 1`). Una llamada HTTP de un servicio a la propia URL se
> autobloquea hasta el timeout (503), así que
> `microservicios.es_llamada_a_si_mismo()` detecta el caso y resuelve el stock
> **en proceso**; con servicios en procesos separados (local) se usa HTTP + token
> como siempre.

## Puertos

| Servicio | Carpeta | Puerto | BD | Tablas |
|---|---|---|---|---|
| Gateway (tienda completa, 90 rutas) | `www/` | 8000 | `DB_NAME` | todas (vista agregada) |
| Inventario | `servicio-inventario/` | 8001 | `MS_INVENTARIO_DB` | `inventario_productos`, `inventario_categorias`, `inventario_proveedores` |
| Ventas | `servicio-ventas/` | 8002 | `MS_VENTAS_DB` | `comercial_pedidos`, `comercial_detalle_pedido`, `comercial_ventas` |
| Usuarios | `servicio-usuarios/` | 8003 | `MS_USUARIOS_DB` | `usuarios_sistema`, `roles` |
| Clientes | `servicio-clientes/` | 8004 | `MS_CLIENTES_DB` | `clientes` |

## BDs

```sql
SOURCE microservicios_bds.sql;
SOURCE microservicios_bds_tablas.sql;
```

## `.env`

```ini
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_NAME=librospe_db
MS_VENTAS_DB=librospe_ms_ventas
MS_INVENTARIO_DB=librospe_ms_inventario
MS_USUARIOS_DB=librospe_ms_usuarios
MS_CLIENTES_DB=librospe_ms_clientes
SERVICE_TOKEN=librospe-interno-dev
MS_INVENTARIO_URL=http://127.0.0.1:8001
```

## Arranque (5 terminales o `run_all.bat`)

```bat
cd www & python app.py                  :: 8000 gateway
cd servicio-inventario & python app.py  :: 8001
cd servicio-ventas & python app.py      :: 8002
cd servicio-usuarios & python app.py    :: 8003
cd servicio-clientes & python app.py    :: 8004
```

## Demo servicio-a-servicio

Ventas consulta stock a Inventario por HTTP (nunca toca su BD):

```
GET http://127.0.0.1:8002/validar-stock/1/2
```

## Diferencia con el monolito

Ver `../Monilitico/README.md`: 1 app + 1 BD, sin tokens ni puertos múltiples.

## Facturación SUNAT (3 modos)

`www/sunat_service.py` emite comprobantes según `SUNAT_MODE` en `.env`:

| Modo | Qué hace | Requisitos |
|---|---|---|
| `simulado` (default) | Hash local + rótulo "AUTORIZACIÓN SUNAT (SIMULADA)" | ninguno |
| `beta` | API `facturacion.apisperu.com` contra ambiente de pruebas SUNAT | `FACTURACION_USER/PASS` (plan apisperu, beta sin certificado) |
| `produccion` | Misma API contra SUNAT producción (XML/CDR reales) | plan apisperu + certificado `.pfx` + usuario SOL secundario |

Si la API falla en `beta`/`produccion`, se hace **fallback automático a
simulado** para no interrumpir ventas. Pasos de la API: `POST /auth/login` →
`POST /invoice` → `GET /invoice/status`. Para pasar a producción: crear cuenta
en apisperu.com, cargar el certificado y clave SOL en su panel y cambiar
`SUNAT_MODE=produccion`.

La validación de clientes ya funciona en todos los modos: DNI (RENIEC) y RUC
(SUNAT) vía `API_PERU_TOKEN`.
