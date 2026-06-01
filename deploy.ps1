# deploy.ps1 - Server-side deploy for the Ask Anton backend.
# Triggered by GitHub Actions over SSH (.github/workflows/deploy.yml). Runs on
# the same Windows box as the Gestura engine.
#
# Model: the Windows Scheduled Task "ask-anton" (SYSTEM, at startup) is the
# SINGLE launcher; it runs start-service.ps1, a supervisor that keeps uvicorn
# alive on port 8001 and restarts it on crash. Deploys apply new code by
# git-resetting, then CYCLING the task (stop -> start) - never by spawning a
# competing process. This means: reboots recover (at-startup trigger), crashes
# recover (supervisor loop), and deploys are a clean restart.
#
# Co-existence with the engine: the server runs as askpython.exe (a renamed
# venv interpreter) - console-subsystem so it starts headless, and invisible to
# the engine's blanket "Get-Process python | Stop-Process". We never blanket-kill.

Write-Host "[ask-deploy] === deploy.ps1 entered ==="
$ErrorActionPreference = "Stop"

$ServerDir = $PSScriptRoot
$Port = 8001
$VenvDir = Join-Path $ServerDir ".venv"
$TaskName = "ask-anton"

# ---- 1. Pull latest --------------------------------------------------------
Write-Host "[ask-deploy] Pulling latest from origin/main..."
Set-Location $ServerDir
git fetch --quiet origin
git reset --hard origin/main
Write-Host ("[ask-deploy] " + (git log -1 --format='%h %s'))
$buildSha = (git rev-parse HEAD).Trim()
Set-Content -Path (Join-Path $ServerDir "BUILD_SHA") -Value $buildSha -Encoding ascii -NoNewline
Write-Host "[ask-deploy] Stamped BUILD_SHA = $buildSha"

if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "[ask-deploy] NOTE: ANTHROPIC_API_KEY not in this session; the task loads it from Machine scope at runtime."
}

# ---- 2. Ensure venv + deps + renamed interpreter ---------------------------
if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    Write-Host "[ask-deploy] Creating venv..."
    python -m venv $VenvDir
}
$venvPy  = Join-Path $VenvDir "Scripts\python.exe"
$venvAsk = Join-Path $VenvDir "Scripts\askpython.exe"
if (-not (Test-Path $venvAsk)) {
    Write-Host "[ask-deploy] Creating askpython.exe (renamed interpreter)..."
    Copy-Item $venvPy $venvAsk -Force
}
Write-Host "[ask-deploy] Installing dependencies..."
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r (Join-Path $ServerDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Host "[ask-deploy] WARNING: pip install exited $LASTEXITCODE (continuing)" }

# Clear bytecode (skip the venv) so each deploy compiles fresh.
Get-ChildItem -Path $ServerDir -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*\.venv\*" } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# ---- 3. Ensure the scheduled task exists with the right settings -----------
# Idempotent: (re)register every deploy so settings/action stay canonical.
# ExecutionTimeLimit 0 = no time cap (the supervisor runs indefinitely);
# IgnoreNew = never run a second copy; restart-on-failure as a backstop.
Write-Host "[ask-deploy] Registering/refreshing scheduled task '$TaskName'..."
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ServerDir\start-service.ps1`"" `
  -WorkingDirectory $ServerDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
  -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Principal $principal -Settings $settings -Force | Out-Null

# ---- 4. Apply new code: cycle the task -------------------------------------
Write-Host "[ask-deploy] Stopping task (kills supervisor + uvicorn)..."
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
# Belt-and-suspenders: free port 8001 if anything is still bound (never a
# blanket kill - only the PID listening on our port).
$portPid = (netstat -ano | Select-String (":" + $Port + "\s.*LISTENING") |
    ForEach-Object { ($_ -split "\s+")[-1] } | Select-Object -First 1)
if ($portPid -and $portPid -ne "0") {
    Stop-Process -Id ([int]$portPid) -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800
}
Write-Host "[ask-deploy] Starting task..."
Start-ScheduledTask -TaskName $TaskName

# ---- 5. Verify it answers (poll; cold start can take a while) --------------
$ok = $false
for ($i = 1; $i -le 16; $i++) {
    Start-Sleep -Seconds 2.5
    try {
        $resp = Invoke-WebRequest -Uri ("http://127.0.0.1:" + $Port + "/build-info") -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) {
            Write-Host "[ask-deploy] Local probe OK (attempt $i): $($resp.Content)"
            $ok = $true; break
        }
    } catch { Write-Host "[ask-deploy] not answering yet (attempt $i of 16)..." }
}
if (-not $ok) {
    Write-Host "[ask-deploy] ERROR: server did not answer on port $Port. Logs:"
    if (Test-Path (Join-Path $ServerDir "uvicorn.err.log")) { Get-Content (Join-Path $ServerDir "uvicorn.err.log") -Tail 40 }
    exit 1
}
Write-Host "[ask-deploy] Deploy complete."
