$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$SSH_HOST = "ssh-librospe.alwaysdata.net"
$SSH_USER = "librospe"
$SSH_KEY = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$WEB_URL = "https://librospe.alwaysdata.net/api/health"

$tarFile = Join-Path $env:TEMP "librospe_deploy.tar.gz"
$eventScript = Join-Path $PSScriptRoot "procesar_eventos.sh"
$venvPy = Join-Path $PSScriptRoot ".venv-live\Scripts\python.exe"

# ---------------- [0/5] Entorno Python: crear venv si falta ----------------
if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Host "Configurando por primera vez: creando .venv-live ..."
    $py = $null
    foreach ($cand in @("py", "python", "python3")) {
        try { & $cand --version 2>$null | Out-Null; $py = $cand; break } catch { }
    }
    if ($null -eq $py) {
        foreach ($glob in @("$env:LOCALAPPDATA\Programs\Python\Python*\python.exe", "C:\ProgramData\Anaconda3\python.exe", "$env:USERPROFILE\anaconda3\python.exe", "$env:USERPROFILE\miniconda3\python.exe")) {
            $f = Get-Item -Path $glob -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($f) { $py = $f.FullName; break }
        }
    }
    if ($null -eq $py) { throw "No se encontro Python. Instalalo antes (python.org o Anaconda)." }
    & $py -m venv .venv-live
    if ($LASTEXITCODE -ne 0) { throw "Fallo al crear .venv-live" }
}
# Con $ErrorActionPreference="Stop", PS 5.1 trata el stderr de un comando nativo
# (p.ej. el traceback de "import paramiko") como error terminante y aborta el script
# antes de llegar a la auto-instalacion. Por eso se ejecuta con EAP en "Continue"
# y se decide por el codigo de salida ($LASTEXITCODE).
$savedEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $venvPy -c "import paramiko" 2>$null | Out-Null
$paramikoFaltante = $LASTEXITCODE -ne 0
$ErrorActionPreference = $savedEAP
if ($paramikoFaltante) {
    Write-Host "Instalando paramiko en el venv ..."
    $ErrorActionPreference = "Continue"
    & $venvPy -m pip install paramiko --quiet
    $rcPip = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    if ($rcPip -ne 0) { throw "Fallo al instalar paramiko" }
}

# ---------------- [0/5] Clave SSH: generar si falta ----------------
if (-not (Test-Path -LiteralPath $SSH_KEY)) {
    Write-Host "Generando clave SSH (no pide contrasena) ..."
    New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh" | Out-Null
    ssh-keygen -t ed25519 -N '""' -C "deploy-librospe" -f $SSH_KEY
    if ($LASTEXITCODE -ne 0) { throw "Fallo al generar la clave SSH" }
}

# ---------------- [0/5] Autorizar clave en el servidor (una sola vez) ----------------
# Los bloques Python se escriben a un archivo temporal y se ejecutan con
# "python archivo.py" en lugar de "python -c". Al pasar codigo como argumento,
# PS 5.1 elimina las comillas dobles embebidas y rompe el codigo.
$pyCheckClave = @"
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import paramiko, sys
host = r'$SSH_HOST'; user = r'$SSH_USER'; key = r'$SSH_KEY'
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(host, username=user, key_filename=key, timeout=30)
    print('KEY_AUTH_OK')
    client.close()
    sys.exit(0)
except Exception as e:
    sys.exit(2)
"@
$tmpPy = Join-Path $env:TEMP "librospe_check_clave.py"
Set-Content -LiteralPath $tmpPy -Value $pyCheckClave -Encoding UTF8
& $venvPy $tmpPy
Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
if ($LASTEXITCODE -eq 2) {
    Write-Host "La clave aun no esta autorizada. Ingresa la contrasena SSH una sola vez:"
    $sec = Read-Host -AsSecureString "Contrasena SSH de alwaysdata"
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    $plain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    $env:LIBROSPE_SSH_PASS = $plain
    $pyAutorizar = @"
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import paramiko, sys
host = r'$SSH_HOST'; user = r'$SSH_USER'; key = r'$SSH_KEY'
passw = os.environ.get('LIBROSPE_SSH_PASS', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(host, username=user, password=passw, timeout=30)
except Exception as e:
    sys.exit("AUTHFAIL: %s" % e)
pub = open(key + '.pub').read().strip()
cmd = 'mkdir -p ~/.ssh && chmod 700 ~/.ssh'
i, o, e = client.exec_command(cmd, timeout=30)
o.read(); rc = o.channel.recv_exit_status()
if rc == 0:
    cmd = "grep -Fq -- '%s' ~/.ssh/authorized_keys 2>/dev/null || echo '%s' >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys" % (pub, pub)
    i, o, e = client.exec_command(cmd, timeout=30)
    o.read(); rc = o.channel.recv_exit_status()
client.close()
sys.exit(0 if rc == 0 else "KEYFAIL")
"@
    $tmpPy = Join-Path $env:TEMP "librospe_autorizar_clave.py"
    Set-Content -LiteralPath $tmpPy -Value $pyAutorizar -Encoding UTF8
    & $venvPy $tmpPy
    Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
    Remove-Item Env:LIBROSPE_SSH_PASS -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0) { throw "No se pudo autorizar la clave SSH. Revisa la contrasena." }
    Write-Host "Clave SSH autorizada en el servidor."
}

# ---------------- [1/5] Empaquetar www/ ----------------
Write-Host "[1/5] Creando paquete www/ ..."
tar.exe -czf $tarFile -C "www" --exclude=__pycache__ --exclude=tmp --exclude=.env .
if ($LASTEXITCODE -ne 0) { throw "Error al crear el tarball" }

# ---------------- [2/5] Subir y desplegar ----------------
Write-Host "[2/5] Subiendo por SFTP a $SSH_HOST ..."
$pySubir = @"
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import paramiko, sys
host = r'$SSH_HOST'; user = r'$SSH_USER'; key = r'$SSH_KEY'
tar = r'$tarFile'; event_script = r'$eventScript'
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, key_filename=key, timeout=60)
sftp = client.open_sftp()
sftp.put(tar, '/home/librospe/deploy.tar.gz')
sftp.put(event_script, '/home/librospe/procesar_eventos.sh.new')
sftp.close()
cmds = [
    'mkdir -p ~/deploy_stage && tar -xzf ~/deploy.tar.gz -C ~/deploy_stage',
    'rsync -a --exclude venv --exclude .env --exclude __pycache__ --exclude logs --exclude instance --exclude tmp --exclude app.log --exclude cookies.txt ~/deploy_stage/ ~/www/',
    'mv ~/procesar_eventos.sh.new ~/procesar_eventos.sh && chmod 750 ~/procesar_eventos.sh',
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
print('Codigo y cron subidos. tmp/restart.txt no reinicia Passenger; usa el panel.')
"@
$tmpPy = Join-Path $env:TEMP "librospe_subir.py"
Set-Content -LiteralPath $tmpPy -Value $pySubir -Encoding UTF8
& $venvPy $tmpPy
Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) { throw "Fallo el deploy por SFTP/SSH" }

# ---------------- [3/5] Verificar ----------------
Write-Host "[3/5] Verificando $WEB_URL ..."
Start-Sleep -Seconds 10
$resp = Invoke-WebRequest -Uri $WEB_URL -UseBasicParsing -TimeoutSec 40
Write-Host ("HTTP {0}: {1}" -f $resp.StatusCode, $resp.Content)

# ---------------- [4/5] Limpiar ----------------
Write-Host "[4/5] Limpiando temporal ..."
Remove-Item -LiteralPath $tarFile -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "============================================================"
Write-Host " DEPLOY COMPLETADO"
Write-Host "============================================================"
Write-Host " IMPORTANTE: reinicia la app en el panel de alwaysdata"
Write-Host " (Web > Sites > librospe > Restart) para que el cambio"
Write-Host " tome efecto. tmp/restart.txt NO reinicia el proceso uWSGI."
Write-Host "============================================================"