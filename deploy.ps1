$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$SSH_HOST = "ssh-librospe.alwaysdata.net"
$SSH_USER = "librospe"
$SSH_KEY = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$WEB_URL = "https://librospe.alwaysdata.net/api/health"

$tarFile = Join-Path $env:TEMP "librospe_deploy.tar.gz"
$venvPy = Join-Path $PSScriptRoot ".venv-live\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Error ".venv-live no existe. Crealo con: python -m venv .venv-live"
}

Write-Host "[1/4] Creando paquete www/ ..."
tar.exe -czf $tarFile -C "www" --exclude=__pycache__ --exclude=tmp --exclude=.env .
if ($LASTEXITCODE -ne 0) { throw "Error al crear el tarball" }

Write-Host "[2/4] Subiendo por SFTP a $SSH_HOST ..."
& $venvPy -c @"
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import paramiko, sys
host = r'$SSH_HOST'; user = r'$SSH_USER'; key = r'$SSH_KEY'
tar = r'$tarFile'
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, key_filename=key, timeout=60)
sftp = client.open_sftp()
sftp.put(tar, '/home/librospe/deploy.tar.gz')
sftp.close()
cmds = [
    'mkdir -p ~/deploy_stage && tar -xzf ~/deploy.tar.gz -C ~/deploy_stage',
    'rsync -a --exclude venv --exclude .env --exclude __pycache__ --exclude logs --exclude instance --exclude tmp --exclude app.log --exclude cookies.txt ~/deploy_stage/ ~/www/',
    'mkdir -p ~/www/tmp && touch ~/www/tmp/restart.txt',
    'rm -rf ~/deploy_stage ~/deploy.tar.gz',
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
print('Codigo subido y WSGI reiniciado (tmp/restart.txt).')
"@
if ($LASTEXITCODE -ne 0) { throw "Fallo el deploy por SFTP/SSH" }

Write-Host "[3/4] Verificando $WEB_URL ..."
Start-Sleep -Seconds 10
$resp = Invoke-WebRequest -Uri $WEB_URL -UseBasicParsing -TimeoutSec 40
Write-Host ("HTTP {0}: {1}" -f $resp.StatusCode, $resp.Content)

Write-Host "[4/4] Limpiando temporal ..."
Remove-Item -LiteralPath $tarFile -Force

Write-Host "Deploy completado."