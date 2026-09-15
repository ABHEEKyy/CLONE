Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$startupFolder = [System.IO.Path]::Combine($env:APPDATA, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
$shortcutPath = Join-Path $startupFolder "Run_Jarvis.lnk"

if (Test-Path $shortcutPath) {
    Remove-Item -Path $shortcutPath -Force
    Write-Host "Removed Run_Jarvis.lnk from Windows Startup folder."
} else {
    Write-Host "No startup shortcut found. Jarvis will only run when opened manually."
}

