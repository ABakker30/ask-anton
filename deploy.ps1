# deploy.ps1 - Server-side deploy for the Ask Anton backend.
# Triggered by GitHub Actions over SSH (see .github/workflows/deploy.yml), the same
# pattern the Gestura engine uses. Runs on the SAME Windows box as the engine.
#
# Co-existence with the engine (important):
#   - The engine binds port 8000; Ask Anton binds 8001.
#   - The engine's deploy does a blanket "Get-Process python | Stop-Process". To avoid
#     being killed by it, Ask Anton runs its venv interpreter under a RENAMED copy,
#     askpython.exe (process name "askpython", which the engine's "python" match does NOT
#     hit). It is console-subsystem (unlike pythonw.exe), so it also starts correctly under
#     the non-interactive SSH deploy and the SYSTEM startup task (pythonw fails in session 0).
#   - This script only ever stops the process LISTENING ON 8001 - never a blanket kill -
#     so it can never take the engine down either.
#   - This script does NOT bounce the shared Cloudflared service (that would blip the
#     engine). Adding the ask.gestura.art ingress rule is a one-time manual step
#     (see README); after that, deploys just restart the 8001 process.

Write-Host "[ask-deploy] === deploy.ps1 entered ==="
$ErrorActionPreference = "Stop"

$ServerDir = $PSScriptRoot
$Port = 8001
$VenvDir = Join-Path $ServerDir ".venv"
$logPath = Join-Path $ServerDir "server.log"
$errPath = Join-Path $ServerDir "server.err.log"

# ---- 1. Pull latest --------------------------------------------------------
Write-Host "[ask-deploy] Pulling latest from origin/main..."
Set-Location $ServerDir
git fetch --quiet origin
git reset --hard origin/main
Write-Host ("[ask-deploy] " + (git log -1 --format='%h %s'))

$buildSha = (git rev-parse HEAD).Trim()
Set-Content -Path (Join-Path $ServerDir "BUILD_SHA") -Value $buildSha -Encoding ascii -NoNewline
Write-Host "[ask-deploy] Stamped BUILD_SHA = $buildSha"

# ---- 2. Sanity: API key present in this session's environment --------------
if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "[ask-deploy] WARNING: ANTHROPIC_API_KEY is not set in this session."
    Write-Host "[ask-deploy] Set it once as a Machine env var so the spawned process inherits it:"
    Write-Host "[ask-deploy]   [Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY','<key>','Machine')"
}

# ---- 3. Ensure venv + dependencies -----------------------------------------
if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    Write-Host "[ask-deploy] Creating venv..."
    python -m venv $VenvDir
}
$venvPy  = Join-Path $VenvDir "Scripts\python.exe"
# Renamed copy of the interpreter: console-subsystem (works headless under SSH/SYSTEM) AND
# invisible to the engine's "Get-Process python" blanket kill.
$venvAsk = Join-Path $VenvDir "Scripts\askpython.exe"
if (-not (Test-Path $venvAsk)) {
    Write-Host "[ask-deploy] Creating askpython.exe (renamed interpreter)..."
    Copy-Item $venvPy $venvAsk -Force
}

Write-Host "[ask-deploy] Installing dependencies..."
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r (Join-Path $ServerDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ask-deploy] WARNING: pip install exited $LASTEXITCODE (continuing)"
}

# ---- 4. Stop ONLY the process on our port (never a blanket kill) -----------
Write-Host "[ask-deploy] Freeing port $Port if in use..."
$portPid = (netstat -ano | Select-String (":" + $Port + "\s.*LISTENING") |
    ForEach-Object { ($_ -split "\s+")[-1] } | Select-Object -First 1)
if ($portPid -and $portPid -ne "0") {
    Stop-Process -Id ([int]$portPid) -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800
}

# Clear bytecode so a new deploy always compiles fresh.
Get-ChildItem -Path $ServerDir -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*\.venv\*" } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# ---- 5. Start detached (survives SSH session close) ------------------------
# Win32_Process.Create spawns outside the SSH job object, so it is not killed
# when GitHub Actions closes the connection. askpython.exe keeps it off the
# engine's "python" kill list while staying console-subsystem. cmd wrapper
# redirects stdout/stderr to logs.
if (Test-Path $logPath) { Clear-Content $logPath }
if (Test-Path $errPath) { Clear-Content $errPath }

Write-Host "[ask-deploy] Starting Ask Anton on port $Port..."
$cmdLine = 'cmd.exe /c "cd /d "' + $ServerDir + '" && "' + $venvAsk + '" -m uvicorn app:app --host 127.0.0.1 --port ' + $Port + ' 1>"' + $logPath + '" 2>"' + $errPath + '""'
$createResult = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmdLine }
if ($createResult.ReturnValue -ne 0) {
    Write-Host "[ask-deploy] ERROR: Win32_Process.Create returned $($createResult.ReturnValue)"
    exit 1
}
Write-Host "[ask-deploy] Spawned wrapper PID $($createResult.ProcessId); waiting for startup..."

# ---- 6. Verify it answers (poll; a cold first start - new venv + imports +
#         corpus load - can take well over 5s, so retry up to ~30s) ----------
$ok = $false
for ($i = 1; $i -le 12; $i++) {
    Start-Sleep -Seconds 2.5
    try {
        $resp = Invoke-WebRequest -Uri ("http://127.0.0.1:" + $Port + "/build-info") -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) {
            Write-Host "[ask-deploy] Local probe OK (attempt $i): $($resp.Content)"
            $ok = $true
            break
        }
    } catch {
        Write-Host "[ask-deploy] not answering yet (attempt $i of 12)..."
    }
}
if (-not $ok) {
    Write-Host "[ask-deploy] ERROR: server did not answer on port $Port after ~30s. Logs:"
    if (Test-Path $errPath) { Get-Content $errPath -Tail 40 }
    exit 1
}

Write-Host "[ask-deploy] Deploy complete."
