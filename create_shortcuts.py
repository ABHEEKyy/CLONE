import os
import sys
import win32com.client

appdata = os.getenv("APPDATA")
userprofile = os.getenv("USERPROFILE")
project_dir = os.path.dirname(os.path.abspath(__file__))
vbs_script = os.path.join(project_dir, "launch_jarvis.vbs")

startup_folder = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")
desktop_folder = os.path.join(userprofile, "Desktop")

shell = win32com.client.Dispatch("WScript.Shell")

icon_path = os.path.join(project_dir, "jarvis_icon.ico")

# 1. Startup Shortcut (Runs silently on PC boot)
startup_lnk_path = os.path.join(startup_folder, "JARVIS_Silent_Wake_Listener.lnk")
shortcut = shell.CreateShortcut(startup_lnk_path)
shortcut.TargetPath = "wscript.exe"
shortcut.Arguments = f'"{vbs_script}"'
shortcut.WorkingDirectory = project_dir
shortcut.IconLocation = icon_path
shortcut.Description = "J.A.R.V.I.S. Automated Startup Background Voice Listener"
shortcut.Save()
print(f"[SUCCESS] Created Startup Shortcut: {startup_lnk_path}")

onedrive_desktop = os.path.join(userprofile, "OneDrive", "Desktop")
target_desktop = onedrive_desktop if os.path.exists(onedrive_desktop) else desktop_folder

# 2. Desktop Shortcut (Manual 1-Click Launch Assistant)
desktop_lnk_path = os.path.join(target_desktop, "J.A.R.V.I.S. Voice Assistant.lnk")
desktop_shortcut = shell.CreateShortcut(desktop_lnk_path)
desktop_shortcut.TargetPath = os.path.join(project_dir, "Run_Jarvis.bat")
desktop_shortcut.WorkingDirectory = project_dir
desktop_shortcut.IconLocation = icon_path
desktop_shortcut.Description = "Launch J.A.R.V.I.S. Voice Assistant"
desktop_shortcut.Save()
print(f"[SUCCESS] Updated Desktop App Shortcut: {desktop_lnk_path}")
