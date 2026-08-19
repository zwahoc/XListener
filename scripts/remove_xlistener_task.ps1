param(
    [string]$TaskName = "XListener Supervisor"
)

$ErrorActionPreference = "Stop"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "XListener Tray" -Confirm:$false -ErrorAction SilentlyContinue
Write-Output "Removed '$TaskName' and 'XListener Tray'."
