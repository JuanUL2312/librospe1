@echo off
REM LibrosPE microservicios - arranca gateway + 4 servicios (5 ventanas)
cd /d %~dp0
start "gateway 8000" cmd /k "cd www & python app.py"
start "inventario 8001" cmd /k "cd servicio-inventario & python app.py"
start "ventas 8002" cmd /k "cd servicio-ventas & python app.py"
start "usuarios 8003" cmd /k "cd servicio-usuarios & python app.py"
start "clientes 8004" cmd /k "cd servicio-clientes & python app.py"
echo 5 servicios lanzados. Verifica: /api/health (8000), /health (8001-8004)
