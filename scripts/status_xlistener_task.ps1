param(
    [string]$TaskName = "XListener Supervisor"
)

$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Output "'$TaskName' is not registered."
    exit 1
}
Get-ScheduledTaskInfo -TaskName $TaskName | Format-List
