# Despliegue de la fase "API Gateway JWT" de LibrosPE a Alwaysdata.
# - Sube www/ (app_api, gateways/, jwt_auth, api_demo, api_cliente.js)
# - Sube los 4 microservicios standalone (con sus correcciones)
# - Instala PyJWT + requests en ~/www/venv
# NO modifica el sitio activo de la tienda (app.py sigue corriendo).
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$SSH_HOST = "ssh-librospe.alwaysdata.net"
$SSH_USER = "librospe"
$SSH_KEY = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$venvPy = Join-Path $PSScriptRoot ".venv-live\Scripts\python.exe"
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
tar.exe -czf $tarFile -C $PSScriptRoot --exclude=__pycache__ --exclude=.env `
    www $servicios
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
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, key_filename=key, timeout=60)
sftp = client.open_sftp()
sftp.put(tar, '/home/librospe/api_deploy.tar.gz')
sftp.close()
cmds = [
    'rm -rf ~/api_stage && mkdir -p ~/api_stage && tar -xzf ~/api_deploy.tar.gz -C ~/api_stage',
    'rsync -a --exclude venv --exclude .env --exclude __pycache__ --exclude logs --exclude instance --exclude tmp --exclude app.log ~/api_stage/www/ ~/www/',
]
for s in servicios.split():
    cmds.append('rsync -a --exclude __pycache__ --exclude .env ~/api_stage/%s/ ~/%s/' % (s, s))
cmds += [
    'mkdir -p ~/www/tmp && touch ~/www/tmp/restart.txt',
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

# ---------------- [3/5] Dependencias en el venv de produccion ----------------
Write-Host "[3/5] Instalando PyJWT + requests en ~/www/venv ..."
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
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(r'$SSH_HOST', username=r'$SSH_USER', key_filename=r'$SSH_KEY', timeout=60)
cmds = [
    '~/www/venv/bin/pip install --quiet PyJWT requests gunicorn',
    "~/www/venv/bin/python -c \"import jwt, requests, gunicorn; print('DEPS_OK', jwt.__version__, requests.__version__, gunicorn.__version__)\"",
    'test -f ~/www/app_api.py && test -f ~/www/jwt_auth.py && test -d ~/www/gateways && test -d ~/www/static/api_demo && test -f ~/servicio-clientes/app.py && echo ARCHIVOS_OK',
]
ok = True
for cmd in cmds:
    i, o, e = client.exec_command(cmd, timeout=300)
    out = o.read().decode('utf-8', 'replace').strip()
    err = e.read().decode('utf-8', 'replace').strip()
    rc = o.channel.recv_exit_status()
    print(('  OK  ' if rc == 0 else '  FALLO ') + out + ((' | ' + err) if err else ''))
    if rc != 0:
        ok = False
client.close()
sys.exit(0 if ok else 1)
"@
$tmpPy = Join-Path $env:TEMP "librospe_api_deps.py"
Set-Content -LiteralPath $tmpPy -Value $pyDeps -Encoding UTF8
& $venvPy $tmpPy
Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de dependencias en produccion" }

# ---------------- [4/5] Verificar HTTP ----------------
Write-Host "[4/5] Verificando que la tienda actual sigue viva + estaticos nuevos ..."
Start-Sleep -Seconds 3
$comprobaciones = @(
    @{ url = "https://librospe.alwaysdata.net/api/health";                 nombre = "health tienda actual" },
    @{ url = "https://librospe.alwaysdata.net/static/js/api_cliente.js";   nombre = "api_cliente.js" },
    @{ url = "https://librospe.alwaysdata.net/static/api_demo/index.html"; nombre = "demo frontend" }
)
$todoOk = $true
foreach ($c in $comprobaciones) {
    try {
        $r = Invoke-WebRequest -Uri $c.url -UseBasicParsing -TimeoutSec 40
        Write-Host ("  HTTP {0} {1}" -f $r.StatusCode, $c.nombre)
        if ($r.StatusCode -ne 200) { $todoOk = $false }
    } catch {
        Write-Host ("  FALLO {0}: {1}" -f $c.nombre, $_.Exception.Message)
        $todoOk = $false
    }
}

# ---------------- [5/5] Resumen ----------------
Remove-Item -LiteralPath $tarFile -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "============================================================"
if ($todoOk) { Write-Host " DEPLOY API COMPLETADO" } else { Write-Host " DEPLOY API CON VERIFICACIONES PENDIENTES" }
Write-Host "============================================================"
Write-Host " Subido: www/ + los cuatro microservicios"
Write-Host " Deps  : PyJWT, requests y gunicorn instalados en ~/www/venv"
Write-Host ""
Write-Host " SIGUIENTE PASO:"
Write-Host "  Registra los cuatro procesos en Advanced > Services de Alwaysdata."
Write-Host "  No uses nohup/cron para mantener procesos web."
Write-Host "  Configura MS_*_URL del Gateway con services-librospe.alwaysdata.net."
Write-Host "  Luego reinicia el sitio y valida /api/health. Ver ACTIVAR_API.md."
Write-Host "============================================================"
