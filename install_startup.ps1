$startupFolder = [System.Environment]::GetFolderPath('Startup')
$shortcutPath1 = Join-Path $startupFolder "System_Wake_Launcher.lnk"
$shortcutPath2 = Join-Path $startupFolder "JARVIS_Silent_Wake_Listener.lnk"

if (Test-Path $shortcutPath1) { Remove-Item $shortcutPath1 -Force }
if (Test-Path $shortcutPath2) { Remove-Item $shortcutPath2 -Force }

Write-Host "✅ JARVIS background voice listener removed from Windows Startup successfully!"
