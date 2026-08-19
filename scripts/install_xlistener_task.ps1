param(
    [string]$TaskName = "XListener Supervisor"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw)) {
    throw "Windowless Python executable not found at $pythonw. Create the virtual environment and install XListener first."
}

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "-m xlistener supervise" -WorkingDirectory $repoRoot
$trayAction = New-ScheduledTaskAction -Execute $pythonw -Argument "-m xlistener tray" -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Register-ScheduledTask -TaskName "XListener Tray" -Action $trayAction -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Output "Registered '$TaskName' and 'XListener Tray' to start at user logon without console windows."
