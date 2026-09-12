import os
import subprocess
import webbrowser
import psutil
from AppOpener import open as open_app

# Common site mappings
DOMAINS = {
    "yt": "https://www.youtube.com",
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "chatgpt": "https://chatgpt.com",
    "reddit": "https://www.reddit.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com"
}

def execute_open_site(site: str, browser: str = "default") -> str:
    clean_site = site.lower().strip().replace("the ", "")
    url = DOMAINS.get(clean_site, clean_site if clean_site.startswith("http") else f"https://{clean_site}.com" if "." in clean_site else f"https://www.google.com/search?q={clean_site}")
    
    b_map = {
        "brave": "brave.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "firefox": "firefox.exe"
    }
    
    b_key = browser.lower().strip()
    if b_key in b_map:
        try:
            subprocess.Popen(f'start {b_map[b_key]} "{url}"', shell=True)
            return f"Opening {site} in {browser.title()}."
        except Exception:
            webbrowser.open(url)
            return f"Opened {site} in default browser."
    else:
        webbrowser.open(url)
        return f"Opening {site} in your default browser."

def execute_launch_app(app_name: str) -> str:
    clean = app_name.lower().strip().replace("the ", "")
    
    # Common quick targets
    quick_targets = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "task manager": "taskmgr.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "explorer": "explorer.exe",
        "settings": "ms-settings:"
    }
    
    if clean in quick_targets:
        try:
            os.startfile(quick_targets[clean])
            return f"Launched {app_name}."
        except Exception:
            pass

    # Start Menu search via AppOpener
    try:
        open_app(clean, match_closest=True, throw_error=True)
        return f"Launched {app_name}."
    except Exception:
        # Fallback to PowerShell
        res = subprocess.run(f'powershell -Command "Start-Process \'{clean}\'"', shell=True, capture_output=True)
        if res.returncode == 0:
            return f"Launched {app_name} via shell."
        return f"Could not find application: {app_name}."

def execute_kill_task(proc_name: str) -> str:
    target = proc_name.lower().replace(".exe", "").strip()
    killed = []
    for proc in psutil.process_iter(['name']):
        try:
            if target in proc.info['name'].lower():
                proc.kill()
                killed.append(proc.info['name'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return f"Terminated: {', '.join(set(killed))}." if killed else f"No process named {proc_name} running."
