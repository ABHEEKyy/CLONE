$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$python = (Get-Command pyw.exe -ErrorAction SilentlyContinue)
if (-not $python) {
    $python = (Get-Command py.exe).Source
} else {
    $python = $python.Source
}

$taskName = "Jarvis Ambient Voice Assistant"
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Unregistered scheduled task '$taskName'."
} else {
    Write-Host "No scheduled startup task found."
}