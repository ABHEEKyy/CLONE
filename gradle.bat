@echo off
if "%1"=="runJarvis" (
    py jarvis_wake_controller.py voice
) else if "%1"=="startBackground" (
    wscript.exe "c:\Users\abhee\arc-task-gen\run_jarvis_background.vbs"
    echo J.A.R.V.I.S. Voice Listener started silently in the background!
) else if "%1"=="installStartup" (
    powershell -ExecutionPolicy Bypass -File "c:\Users\abhee\arc-task-gen\install_startup.ps1"
) else if "%1"=="runJarvisText" (
    py jarvis_wake_controller.py text
) else if "%1"=="testJarvisCmd" (
    py -c "import jarvis_wake_controller; jarvis_wake_controller.process_command('Run PowerShell Get-Date')"
) else if "%1"=="checkOllama" (
    powershell -NoProfile -Command "Invoke-RestMethod -Uri http://localhost:11434/api/tags"
) else (
    echo Available tasks: runJarvis, startBackground, installStartup, runJarvisText, testJarvisCmd, checkOllama
)
