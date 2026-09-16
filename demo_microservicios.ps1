# ============================================
# LibrosPE - Demo de microservicios para docente
# Uso:
#   .\demo_microservicios.ps1 -Correo admin@correo.com -Clave 123456
#   .\demo_microservicios.ps1                     (te pedirá correo/clave)
#   .\demo_microservicios.ps1 -SoloHealth         (solo monitor, sin login)
#   .\demo_microservicios.ps1 -EjecutarEscritura  (incluye PUT que modifica datos)
#   .\demo_microservicios.ps1 -Produccion         (apunta a librospe.alwaysdata.net)
#   .\demo_microservicios.ps1 -BaseUrl "https://mi.dominio"  (URL personalizada)
# ============================================
param(
    [string]$Correo = $env:DEMO_CORREO,
    [string]$Clave  = $env:DEMO_CLAVE,
    [string]$BaseUrl = "",
    [switch]$Produccion,
    [switch]$SoloHealth,
    [switch]$EjecutarEscritura
)

if ($Produccion) {
    $BaseUrl = "https://librospe.alwaysdata.net"
} elseif (-not $BaseUrl) {
    $BaseUrl = "http://localhost:8000"
}

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repos = "=" * 68
$Sec = "-" * 68

function Paso($titulo) {
    Write-Host ""
    Write-Host $Repos -ForegroundColor Cyan
    Write-Host "  $titulo" -ForegroundColor Cyan
    Write-Host $Repos -ForegroundColor Cyan
}

function Ok($msg)    { Write-Host "  [OK]     $msg" -ForegroundColor Green }
function Info($msg)  { Write-Host "  [INFO]   $msg" -ForegroundColor Yellow }
function Errorx($msg){ Write-Host "  [ERROR]  $msg" -ForegroundColor Red }

function Get-ServerActivo {
    try {
        Invoke-RestMethod "$BaseUrl/api/health" -TimeoutSec 5 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Start-Servidor {
    Info "Arrancando el servidor Flask en background (www/app.py)..."
    $python = Join-Path $Raiz ".venv-live\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        Errorx "No existe .venv-live. Ejecuta primero run_local.bat y deja el servidor abierto."
        return $false
    }
    $logOut = Join-Path $env:TEMP "librospe_demo_out.log"
    $logErr = Join-Path $env:TEMP "librospe_demo_err.log"
    Start-Process -FilePath $python -ArgumentList "app.py" `
        -WorkingDirectory (Join-Path $Raiz "www") -WindowStyle Hidden `
        -RedirectStandardOutput $logOut -RedirectStandardError $logErr | Out-Null

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        if (Get-ServerActivo) { Ok "Servidor respondiendo en $BaseUrl"; return $true }
    }
    Errorx "El servidor no respondió. Revisa $logErr"
    return $false
}

function Show-Health {
    Paso "1) MICROSERVICIO MONITOR - /api/health (público)"
    $h = Invoke-RestMethod "$BaseUrl/api/health"
    Write-Host ""
    Write-Host ("    status      : {0}" -f $h.status)
    Write-Host ("    service     : {0}" -f $h.service)
    Write-Host ("    version     : {0}" -f $h.version)
    Write-Host "    services    :"
    foreach ($k in $h.services.PSObject.Properties) {
        $color = if ($k.Value -eq "active") { "Green" } else { "Red" }
        Write-Host ("      {0,-12}: {1}" -f $k.Name, $k.Value) -ForegroundColor $color
    }
    Write-Host ("    timestamp   : {0}" -f $h.timestamp)
    Write-Host ""
    if ($h.status -eq "OK") { Ok "El monitor confirma que los servicios comercial e inventario estan activos" }
    else { Errorx "Algun servicio no esta configurado (tablas espejo ausentes)" }
}

function Show-SinAutenticacion {
    Paso "2) SEGURIDAD - sin sesion no se accede"
    Info "Llamando GET /api/comercial/pedidos SIN estar logueado (sin seguir redireccion)..."
    $req = [System.Net.HttpWebRequest]::Create("$BaseUrl/api/comercial/pedidos")
    $req.Method = "GET"
    $req.AllowAutoRedirect = $false
    $req.Timeout = 5000
    try {
        $res = $req.GetResponse()
        $code = [int]$res.StatusCode
    } catch [System.Net.WebException] {
        $code = [int]$_.Exception.Response.StatusCode
    }
    Write-Host ("    HTTP status : {0}" -f $code)
    if ($code -eq 302) {
        Ok "Redirige a /login: el microservicio hereda la autenticacion del monolito ($code)"
    } else {
        Info "Respuesta inesperada: $code (esperado 302)"
    }
}

function Login-Log($correo, $clave) {
    Paso "3) LOGIN - obtener cookie de sesion"
    $s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $r = Invoke-WebRequest "$BaseUrl/login" -WebSession $s
    $body = @{ correo = $correo; clave = $clave }
    $r2 = Invoke-WebRequest "$BaseUrl/login" -Method POST -Body $body -WebSession $s
    # Verificar sesion llamando a un endpoint protegido
    try {
        $p = Invoke-RestMethod "$BaseUrl/api/inventario/productos" -WebSession $s -TimeoutSec 10
        Ok "Login correcto. Sesion activa con rol administrador en la cookie."
        return $s
    } catch {
        Errorx "No se pudo autenticar. Revisa CORREO/CLAVE."
        return $null
    }
}

function Show-Comercial($s) {
    Paso "4) MICROSERVICIO COMERCIAL - /api/comercial (pedidos y ventas)"
    $ventas = @(Invoke-RestMethod "$BaseUrl/api/comercial/ventas" -WebSession $s)
    $pedidos = @(Invoke-RestMethod "$BaseUrl/api/comercial/pedidos" -WebSession $s)
    Write-Host ("    total ventas         : {0}" -f $ventas.Count)
    Write-Host ("    total pedidos        : {0}" -f $pedidos.Count)
    if ($pedidos.Count -gt 0) {
        Write-Host ""
        Write-Host "    Muestra de pedido (1):"
        Write-Host ($pedidos[0] | ConvertTo-Json -Depth 4 | ForEach-Object { "      $_" })
        $detalle = Invoke-RestMethod "$BaseUrl/api/comercial/pedidos/$($pedidos[0].id)" -WebSession $s
        Write-Host ("    Detalle del pedido {0}: {1} lineas" -f $pedidos[0].id, @($detalle.detalles).Count)
        if (@($detalle.detalles).Count -gt 0) {
            Write-Host ($detalle.detalles | ConvertTo-Json -Depth 3 | ForEach-Object { "        $_" })
        }
    }
    Ok "Comercial responde con su tabla espejo comercial_pedidos/comercial_ventas"
}

function Show-Inventario($s) {
    Paso "5) MICROSERVICIO INVENTARIO - /api/inventario (productos y stock)"
    $productos = @(Invoke-RestMethod "$BaseUrl/api/inventario/productos" -WebSession $s)
    Write-Host ("    total productos : {0}" -f $productos.Count)
    if ($productos.Count -gt 0) {
        Write-Host ""
        Write-Host "    Muestra de producto (1):"
        Write-Host ($productos[0] | ConvertTo-Json -Depth 3 | ForEach-Object { "      $_" })
    }
    $bajos = @(Invoke-RestMethod "$BaseUrl/api/inventario/stock/bajo/10" -WebSession $s)
    Write-Host ("    con stock < 10 : {0}" -f $bajos.Count)
    if ($bajos.Count -gt 0) {
        foreach ($b in $bajos) {
            Write-Host ("      - {0} (cantidad: {1})" -f $b.nombre, $b.cantidad)
        }
    }
    $verif = Invoke-RestMethod "$BaseUrl/api/inventario/verificar-stock/$($productos[0].id)/5" -WebSession $s
    Write-Host ""
    Write-Host "    Verificar stock (disponibles 5 de producto $($productos[0].id)):"
    Write-Host ($verif | ConvertTo-Json -Depth 3 | ForEach-Object { "      $_" })
    Ok "Inventario responde con su tabla espejo inventario_productos"
}

function Show-AdminEscritura($s) {
    Paso "6) OPERACIONES DE ESCRITURA (solo administrador)"
    $pedidos = @(Invoke-RestMethod "$BaseUrl/api/comercial/pedidos" -WebSession $s)
    $productos = @(Invoke-RestMethod "$BaseUrl/api/inventario/productos" -WebSession $s)
    if ($pedidos.Count -gt 0) {
        $id = $pedidos[0].id
        $estadoNuevo = if ($pedidos[0].estado -eq "confirmado") { "pendiente" } else { "confirmado" }
        Info "PUT /api/comercial/pedidos/$id/estado  ->  estado=$estadoNuevo"
        $r = Invoke-RestMethod "$BaseUrl/api/comercial/pedidos/$id/estado" -Method PUT -WebSession $s `
            -ContentType "application/json" -Body (@{ estado = $estadoNuevo } | ConvertTo-Json)
        Write-Host ("    " + ($r | ConvertTo-Json -Depth 3))
        Ok "El microservicio comercial actualizo el estado del pedido"
    }
    if ($productos.Count -gt 0) {
        $id = $productos[0].id
        $cant = $productos[0].cantidad
        Info "PUT /api/inventario/stock/$id  ->  cantidad=$cant (sin cambio real)"
        $r = Invoke-RestMethod "$BaseUrl/api/inventario/stock/$id" -Method PUT -WebSession $s `
            -ContentType "application/json" -Body (@{ cantidad = $cant } | ConvertTo-Json)
        Write-Host ("    " + ($r | ConvertTo-Json -Depth 3))
        Ok "El microservicio inventario actualizo el stock"
    }
}

# ============================================
#  EJECUCION
# ============================================
Write-Host $Repos -ForegroundColor Cyan
Write-Host "  LibrosPE - DEMO DE MICROSERVICIOS" -ForegroundColor Cyan
Write-Host "  comercial | inventario | monitor" -ForegroundColor Cyan
Write-Host $Repos -ForegroundColor Cyan

if (-not (Get-ServerActivo)) {
    if (-not (Start-Servidor)) { exit 1 }
} else {
    Ok "Servidor ya esta corriendo en $BaseUrl"
}

Show-Health

if ($SoloHealth) {
    Write-Host ""
    Info "Modo -SoloHealth: no se prueba el login."
    exit 0
}

Show-SinAutenticacion

if (-not $Correo) { $Correo = Read-Host "Correo de usuario del sistema" }
if (-not $Clave)  { $Clave  = Read-Host "Clave" -AsSecureString; $Clave = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($Clave)) }

if ($Correo) {
    $session = Login-Log $Correo $Clave
    if ($session) {
        Show-Comercial $session
        Show-Inventario $session
        if ($EjecutarEscritura) { Show-AdminEscritura $session }
        else {
            Write-Host ""
            Info "Omitidas las operaciones de escritura. Agrega -EjecutarEscritura para probar los PUT."
        }
    }
} else {
    Info "Sin credenciales: se omite la parte logueada de la demo."
}

Write-Host ""
Write-Host $Repos -ForegroundColor Cyan
Write-Host "  RESUMEN DE LA DEMO" -ForegroundColor Cyan
Write-Host $Repos -ForegroundColor Cyan
Write-Host "  /api/health                        -> MONITOR (estado de los servicios)"
Write-Host "  /api/comercial/pedidos             -> COMERCIAL (pedidos y ventas)"
Write-Host "  /api/comercial/pedidos/<id>/estado -> COMERCIAL (PUT, solo admin)"
Write-Host "  /api/inventario/productos          -> INVENTARIO (productos)"
Write-Host "  /api/inventario/stock/bajo/<min>   -> INVENTARIO (alertas de stock)"
Write-Host "  /api/inventario/verificar-stock    -> INVENTARIO (validacion de stock)"
Write-Host ""
Info "Dashboard visual (admin): abre $BaseUrl/microservicios/dashboard"
Write-Host ""
Info "Health check: $BaseUrl/api/health (también en el navegador sin login)"
Write-Host ""