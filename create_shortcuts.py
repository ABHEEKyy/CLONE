import os
import sys
import win32com.client

appdata = os.getenv("APPDATA")
userprofile = os.getenv("USERPROFILE")
project_dir = os.path.dirname(os.path.abspath(__file__))

startup_folder = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")
desktop_folder = os.path.join(userprofile, "Desktop")

shell = win32com.client.Dispatch("WScript.Shell")
icon_path = os.path.join(project_dir, "jarvis_icon.ico")

# Remove any Startup shortcuts so listener does NOT launch at Windows startup
for old_name in ["JARVIS_Voice_Assistant_Startup.lnk", "System_Wake_Launcher.lnk", "JARVIS_Silent_Wake_Listener.lnk", "Run_Jarvis.lnk"]:
    old_path = os.path.join(startup_folder, old_name)
    if os.path.exists(old_path):
        try:
            os.remove(old_path)
            print(f"[SUCCESS] Removed Startup Shortcut: {old_path}")
        except Exception as e:
            print(f"[WARNING] Could not remove startup shortcut: {e}")

# 2. Desktop Shortcut (Manual 1-Click Launch Assistant)
onedrive_desktop = os.path.join(userprofile, "OneDrive", "Desktop")
target_desktop = onedrive_desktop if os.path.exists(onedrive_desktop) else desktop_folder

desktop_lnk_path = os.path.join(target_desktop, "J.A.R.V.I.S. Voice Assistant.lnk")
desktop_shortcut = shell.CreateShortcut(desktop_lnk_path)
desktop_shortcut.TargetPath = os.path.join(project_dir, "Run_Jarvis.bat")
desktop_shortcut.WorkingDirectory = project_dir
desktop_shortcut.IconLocation = icon_path
desktop_shortcut.Description = "Launch J.A.R.V.I.S. Voice Assistant"
desktop_shortcut.Save()
print(f"[SUCCESS] Updated Desktop App Shortcut: {desktop_lnk_path}")
