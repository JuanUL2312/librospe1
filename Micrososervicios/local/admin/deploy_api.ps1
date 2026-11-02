# Despliegue de archivos del Gateway JWT a Alwaysdata.
# Copia www/ a ~/api_gateway; no reemplaza ~/www/app.py ni reinicia la tienda.
# Sube los cuatro microservicios, sincronizar_copias.sql y dos migraciones.
# Instala dependencias aisladas en ~/api_gateway/venv; no ejecuta migraciones.
$ErrorActionPreference = "Stop"
$Raiz = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $Raiz

$SSH_HOST = "ssh-librospe.alwaysdata.net"
$SSH_USER = "librospe"
$SSH_KEY = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$venvPy = Join-Path $Raiz ".venv-live\Scripts\python.exe"
$tarFile = Join-Path $env:TEMP "librospe_api_deploy.tar.gz"
$servicios = @("servicio-inventario", "servicio-ventas", "servicio-usuarios", "servicio-clientes")

# ---------------- [0/5] paramiko ----------------
$ErrorActionPreference = "Continue"
& $venvPy -c "import paramiko" 2>$null | Out-Null
$falta = $LASTEXITCODE -ne 0
$ErrorActionPreference = "Stop"
if ($falta) {
    $ErrorActionPreference = "Continue"
    & $venvPy -m pip install paramiko --quiet
    $rc = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($rc -ne 0) { throw "Fallo al instalar paramiko" }
}

# ---------------- [1/5] Empaquetar ----------------
Write-Host "[1/5] Creando paquete www/ + servicios ..."
tar.exe -czf $tarFile -C $Raiz --exclude=__pycache__ --exclude=.env `
    www $servicios sincronizar_copias.sql `
    database/migrations/migracion_eliminar_clientes_inventario.sql `
    database/migrations/migracion_ventas_espejo_inventario.sql
if ($LASTEXITCODE -ne 0) { throw "Error al crear el tarball" }

# ---------------- [2/5] Subir ----------------
Write-Host "[2/5] Subiendo por SFTP a $SSH_HOST ..."
$pySubir = @"
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import paramiko
host = r'$SSH_HOST'; user = r'$SSH_USER'; key = r'$SSH_KEY'
tar = r'$tarFile'
servicios = r'$($servicios -join " ")'
client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect(host, username=user, key_filename=key, timeout=60)
sftp = client.open_sftp()
sftp.put(tar, '/home/librospe/api_deploy.tar.gz')
sftp.close()
cmds = [
    'rm -rf ~/api_stage && mkdir -p ~/api_stage && tar -xzf ~/api_deploy.tar.gz -C ~/api_stage',
    'mkdir -p ~/api_gateway && rsync -a --exclude venv --exclude .env --exclude __pycache__ --exclude logs --exclude instance --exclude tmp --exclude app.log ~/api_stage/www/ ~/api_gateway/',
    'cp ~/api_gateway/passenger_api_gateway_wsgi.py ~/api_gateway/passenger_wsgi.py',
]
for s in servicios.split():
    cmds.append('rsync -a --exclude __pycache__ --exclude .env ~/api_stage/%s/ ~/%s/' % (s, s))
cmds += [
    'rsync -a ~/api_stage/sincronizar_copias.sql ~/sincronizar_copias.sql',
    'rsync -a ~/api_stage/database/migrations/migracion_eliminar_clientes_inventario.sql ~/migracion_eliminar_clientes_inventario.sql',
    'rsync -a ~/api_stage/database/migrations/migracion_ventas_espejo_inventario.sql ~/migracion_ventas_espejo_inventario.sql',
    'rm -rf ~/api_stage ~/api_deploy.tar.gz',
]
for cmd in cmds:
    i, o, e = client.exec_command(cmd, timeout=300)
    err = e.read().decode('utf-8', 'replace')
    rc = o.channel.recv_exit_status()
    if rc != 0:
        print('FALLO: ' + cmd + '\n' + err)
        client.close()
        sys.exit(1)
client.close()
print('Codigo subido.')
"@
$tmpPy = Join-Path $env:TEMP "librospe_api_subir.py"
Set-Content -LiteralPath $tmpPy -Value $pySubir -Encoding UTF8
& $venvPy $tmpPy
Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) { throw "Fallo el deploy por SFTP/SSH" }

# ---------------- [3/5] Dependencias aisladas del sitio activo ----------------
Write-Host "[3/5] Preparando entorno virtual en ~/api_gateway/venv ..."
$pyDeps = @"
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import paramiko
client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect(r'$SSH_HOST', username=r'$SSH_USER', key_filename=r'$SSH_KEY', timeout=60)
cmds = [
    'python3 -m venv ~/api_gateway/venv',
    '~/api_gateway/venv/bin/pip install --quiet Flask==2.3.3 Flask-Bcrypt==1.0.1 Flask-SQLAlchemy==3.1.1 PyMySQL==1.1.3 SQLAlchemy==2.0.49 Werkzeug==2.3.8 pika==1.3.2 PyJWT==2.15.1 requests==2.34.2 gunicorn==26.0.0',
    "~/api_gateway/venv/bin/python -c \"import flask, flask_bcrypt, flask_sqlalchemy, pymysql, sqlalchemy, pika, jwt, requests, gunicorn; print('DEPS_OK')\"",
    'test -f ~/api_gateway/app_api.py && test -f ~/api_gateway/jwt_auth.py && test -d ~/api_gateway/gateways && test -d ~/api_gateway/static/api_demo && test -f ~/servicio-clientes/app.py && echo ARCHIVOS_OK',
]
ok = True
for cmd in cmds:
    i, o, e = client.exec_command(cmd, timeout=300)
    out = o.read().decode('utf-8', 'replace').strip()
    err = e.read().decode('utf-8', 'replace').strip()
    rc = o.channel.recv_exit_status()
    print(('  OK  ' if rc == 0 else '  FALLO ') + (out or cmd) + ((' | ' + err) if err else ''))
    if rc != 0:
        ok = False
client.close()
sys.exit(0 if ok else 1)
"@
$tmpPy = Join-Path $env:TEMP "librospe_api_deps.py"
Set-Content -LiteralPath $tmpPy -Value $pyDeps -Encoding UTF8
& $venvPy $tmpPy
Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) { throw "Fallo la preparacion del entorno aislado" }

# ---------------- [4/5] Verificar que la tienda sigue activa ----------------
Write-Host "[4/5] Comprobando que la tienda actual sigue respondiendo ..."
Start-Sleep -Seconds 3
$todoOk = $true
try {
    $r = Invoke-WebRequest -Uri "https://librospe.alwaysdata.net/" -UseBasicParsing -TimeoutSec 40
    Write-Host ("  HTTP {0} tienda activa" -f $r.StatusCode)
    if ($r.StatusCode -ne 200) { $todoOk = $false }
} catch {
    Write-Host ("  FALLO tienda activa: {0}" -f $_.Exception.Message)
    $todoOk = $false
}

# ---------------- [5/5] Resumen ----------------
Remove-Item -LiteralPath $tarFile -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "============================================================"
if ($todoOk) {
    Write-Host " ARCHIVOS API DESPLEGADOS; TIENDA ACTIVA SIN REINICIAR"
} else {
    Write-Host " ARCHIVOS DESPLEGADOS; VERIFICAR RESPUESTA DE LA TIENDA"
}
Write-Host "============================================================"
Write-Host " Gateway: ~/api_gateway (todavÃ­a no activado)"
Write-Host " Servicios: ~/servicio-inventario, ~/servicio-ventas,"
Write-Host "            ~/servicio-usuarios, ~/servicio-clientes"
Write-Host " Dependencias: instaladas en ~/api_gateway/venv"
Write-Host ""
Write-Host " SIGUIENTE PASO:"
Write-Host "  Configura los cuatro microservicios y el Gateway como servicios administrados."
Write-Host "  Usa ~/api_gateway/venv/bin/gunicorn para arrancar los procesos."
Write-Host "  No reinicies la tienda hasta planificar su activaciÃ³n."
Write-Host "============================================================"

