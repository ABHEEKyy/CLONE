$startupFolder = [System.Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder "System_Wake_Launcher.lnk"
$scriptPath = "c:\Users\abhee\arc-task-gen\hybrid_listener.py"


$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = "C:\Users\abhee\AppData\Local\Programs\Python\Python313\pythonw.exe"
$Shortcut.Arguments = "`"$scriptPath`""
$Shortcut.WorkingDirectory = "c:\Users\abhee\arc-task-gen"
$Shortcut.Description = "Silently listens for 'wake up' to automatically start Run_Jarvis.bat in CMD"
$Shortcut.Save()



Write-Host "✅ System Wake Launcher added to Windows Startup folder successfully!"
Write-Host "Shortcut created at: $shortcutPath"
