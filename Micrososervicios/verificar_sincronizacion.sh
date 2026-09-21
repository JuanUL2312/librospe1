#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"

if [[ ! -r "$ENV_FILE" ]]; then
  echo "No se encontró el archivo de configuración: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a
: "${DB_USER:?Falta DB_USER}" "${DB_PASSWORD:?Falta DB_PASSWORD}" "${DB_HOST:?Falta DB_HOST}" "${DB_NAME:?Falta DB_NAME}"

echo "========================================="
echo "📊 ESTADO DE SINCRONIZACIÓN"
echo "========================================="

MYSQL_PWD="$DB_PASSWORD" mysql --host="$DB_HOST" --user="$DB_USER" "$DB_NAME" << 'SQL'
SELECT 
    'PEDIDOS' AS tabla,
    (SELECT COUNT(*) FROM pedidos) AS origen,
    (SELECT COUNT(*) FROM comercial_pedidos) AS destino,
    CASE 
        WHEN (SELECT COUNT(*) FROM pedidos) = (SELECT COUNT(*) FROM comercial_pedidos) 
        THEN '✅ Sincronizado'
        ELSE '⚠️ Pendiente'
    END AS estado
UNION ALL
SELECT 
    'DETALLES',
    (SELECT COUNT(*) FROM detalle_pedido),
    (SELECT COUNT(*) FROM comercial_detalle_pedido),
    CASE 
        WHEN (SELECT COUNT(*) FROM detalle_pedido) = (SELECT COUNT(*) FROM comercial_detalle_pedido) 
        THEN '✅ Sincronizado'
        ELSE '⚠️ Pendiente'
    END
UNION ALL
SELECT 
    'PRODUCTOS',
    (SELECT COUNT(*) FROM productos),
    (SELECT COUNT(*) FROM inventario_productos),
    CASE 
        WHEN (SELECT COUNT(*) FROM productos) = (SELECT COUNT(*) FROM inventario_productos) 
        THEN '✅ Sincronizado'
        ELSE '⚠️ Pendiente'
    END
UNION ALL
SELECT 
    'PROVEEDORES',
    (SELECT COUNT(*) FROM proveedores),
    (SELECT COUNT(*) FROM inventario_proveedores),
    CASE 
        WHEN (SELECT COUNT(*) FROM proveedores) = (SELECT COUNT(*) FROM inventario_proveedores) 
        THEN '✅ Sincronizado'
        ELSE '⚠️ Pendiente'
    END;
SQL

echo "========================================="
