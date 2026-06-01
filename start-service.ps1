# start-service.ps1 - boot launcher for Ask Anton.
# Used by the "ask-anton" Windows Scheduled Task (runs as SYSTEM at startup); also
# runnable by hand. Registration (one-time):
#   $a = New-ScheduledTaskAction -Execute "powershell.exe" `
#        -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\ask-anton\start-service.ps1" `
#        -WorkingDirectory "C:\ask-anton"
#   $t = New-ScheduledTaskTrigger -AtStartup
#   $p = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
#   Register-ScheduledTask -TaskName "ask-anton" -Action $a -Trigger $t -Principal $p -Force
#
# Key choices:
#   - Loads secrets from Machine-scope env into the process, so it does NOT depend on the
#     Task Scheduler service's (possibly stale) environment block.
#   - Launches the venv interpreter under the RENAMED copy askpython.exe: console-subsystem
#     (pythonw.exe fails when launched by SYSTEM in non-interactive "session 0"), and
#     invisible to the engine's "Get-Process python" blanket kill.
#   - Redirects output to logs (no console under SYSTEM).

$ErrorActionPreference = "Continue"
$here = $PSScriptRoot
$log  = Join-Path $here "start-service.log"
"=== start-service launched $(Get-Date) (user=$env:USERNAME) ===" | Out-File $log -Encoding ascii

foreach ($n in 'ANTHROPIC_API_KEY','TURNSTILE_SECRET','TURNSTILE_SITEKEY') {
    $v = [Environment]::GetEnvironmentVariable($n,'Machine')
    if ($v) { [Environment]::SetEnvironmentVariable($n,$v,'Process') }
}
("key length = " + ([Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','Process')).Length) | Out-File $log -Append -Encoding ascii

$venvPy  = Join-Path $here ".venv\Scripts\python.exe"
$venvAsk = Join-Path $here ".venv\Scripts\askpython.exe"
if ((Test-Path $venvPy) -and -not (Test-Path $venvAsk)) { Copy-Item $venvPy $venvAsk -Force }

Set-Location $here
& $venvAsk -m uvicorn app:app --host 127.0.0.1 --port 8001 1>> (Join-Path $here "uvicorn.out.log") 2>> (Join-Path $here "uvicorn.err.log")
("uvicorn exited code = " + $LASTEXITCODE) | Out-File $log -Append -Encoding ascii
