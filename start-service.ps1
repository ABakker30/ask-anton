# start-service.ps1 - resilient launcher for Ask Anton.
# Run by the "ask-anton" Windows Scheduled Task (SYSTEM, at startup). It is a
# SUPERVISOR: it keeps uvicorn alive, restarting it on crash with a short
# backoff, so a transient failure (boot-time race, OOM, etc.) self-heals
# instead of leaving ask.gestura.art down until the next deploy/reboot.
#
# The task is the single launcher; deploy.ps1 applies new code by cycling the
# task (Stop/Start), never by spawning a competing process.
#
# Key choices:
#   - Loads secrets from Machine-scope env (independent of the Task Scheduler
#     service environment).
#   - Runs the venv interpreter as the renamed askpython.exe: console-subsystem
#     (works headless under SYSTEM/SSH) and invisible to the engine's blanket
#     "Get-Process python" kill.

$ErrorActionPreference = "Continue"
$here = $PSScriptRoot
$log  = Join-Path $here "start-service.log"
"=== supervisor started $(Get-Date) (user=$env:USERNAME) ===" | Out-File $log -Encoding ascii

foreach ($n in 'ANTHROPIC_API_KEY','TURNSTILE_SECRET','TURNSTILE_SITEKEY') {
    $v = [Environment]::GetEnvironmentVariable($n,'Machine')
    if ($v) { [Environment]::SetEnvironmentVariable($n,$v,'Process') }
}
("key length = " + ([Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','Process')).Length) | Out-File $log -Append -Encoding ascii

$venvPy  = Join-Path $here ".venv\Scripts\python.exe"
$venvAsk = Join-Path $here ".venv\Scripts\askpython.exe"
if ((Test-Path $venvPy) -and -not (Test-Path $venvAsk)) { Copy-Item $venvPy $venvAsk -Force }

Set-Location $here

# Supervisor loop: keep the server up. uvicorn normally runs forever; if it
# ever exits (crash, killed), log it and relaunch after a short backoff.
while ($true) {
    ("--- launching uvicorn $(Get-Date) ---") | Out-File $log -Append -Encoding ascii
    & $venvAsk -m uvicorn app:app --host 127.0.0.1 --port 8001 1>> (Join-Path $here "uvicorn.out.log") 2>> (Join-Path $here "uvicorn.err.log")
    ("uvicorn exited code=" + $LASTEXITCODE + " at $(Get-Date); restarting in 3s") | Out-File $log -Append -Encoding ascii
    Start-Sleep -Seconds 3
}
