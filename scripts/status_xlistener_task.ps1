param(
    [string]$TaskName = "XListener Supervisor"
)

$ErrorActionPreference = "Stop"
foreach ($name in @($TaskName, "XListener Tray")) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Output "'$name' is not registered."
        continue
    }
    Write-Output "--- $name ---"
    Get-ScheduledTaskInfo -TaskName $name | Format-List
}
