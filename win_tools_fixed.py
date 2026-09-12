import os
import subprocess
import webbrowser

def find_file_by_name_or_partial(query_name: str) -> str | None:
    """Finds any app, shortcut (.lnk), or file on Desktop, Start Menu, workspace, or user library matching full or partial name regardless of extension."""
    raw = query_name.lower().strip()
    for prefix in ["open ", "launch ", "start ", "run ", "the ", "file ", "folder ", "script ", "app "]:
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()
    
    if not raw:
        return None

    if os.path.exists(raw):
        return os.path.abspath(raw)

    clean_raw = raw.replace("_", " ").replace("-", " ").strip()
    compressed_raw = clean_raw.replace(" ", "")

    user_home = os.path.expanduser("~")
    workspace_root = os.getcwd()
    search_dirs = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, r"OneDrive\Desktop"),
        r"C:\Users\Public\Desktop",
        os.path.join(user_home, r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",

        workspace_root,
        os.path.abspath(os.path.join(workspace_root, "..")),
        os.path.join(user_home, "Downloads"),
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, r"OneDrive\Documents"),
        os.path.join(user_home, "Pictures"),
        os.path.join(user_home, "Videos"),
        user_home,
    ]

    matches = []
    seen = set()

    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        try:
            for root, dirs, files in os.walk(s_dir):
                for item in files + dirs:
                    full_path = os.path.abspath(os.path.join(root, item))
                    if full_path in seen:
                        continue
                    
                    item_lower = item.lower()
                    base_name, ext = os.path.splitext(item_lower)
                    
                    # Clean shortcut suffixes e.g. 'forzahorizon6 - Shortcut' -> 'forzahorizon6'
                    clean_item_base = base_name.replace(" - shortcut", "").replace("-shortcut", "").replace("(shortcut)", "").replace("_", " ").replace("-", " ").strip()
                    item_compressed = clean_item_base.replace(" ", "")

                    score = 0
                    if raw == item_lower or raw == base_name or clean_raw == clean_item_base or compressed_raw == item_compressed:
                        score = 100
                    elif raw in item_lower or raw in base_name or clean_raw in clean_item_base or compressed_raw in item_compressed:
                        score = 85
                    elif item_compressed in compressed_raw:
                        score = 80
                    else:
                        words = [w for w in clean_raw.split() if len(w) > 1]
                        if words and all(w in clean_item_base or w in item_compressed for w in words):
                            score = 75

                    if score > 0:
                        is_dir = os.path.isdir(full_path)
                        is_desktop_or_start = any(k in full_path.lower() for k in ["desktop", "start menu"])
                        
                        # Priority: Desktop/Start Menu shortcut (.lnk) = +150, .exe/.bat/.cmd = +100, file = +40, dir = +0
                        location_bonus = 150 if (ext == ".lnk" and is_desktop_or_start) else 120 if ext == ".lnk" else 100 if ext in [".exe", ".bat", ".cmd", ".ps1"] else 40 if not is_dir else 0
                        final_score = score + location_bonus
                        
                        seen.add(full_path)
                        matches.append((final_score, full_path))

                if root.count(os.sep) - s_dir.count(os.sep) >= 3:
                    del dirs[:]
        except Exception:
            continue

    if matches:
        matches.sort(key=lambda x: x[0], reverse=True)
        return matches[0][1]

    return None



def resolve_app_command(app_query: str) -> str:
    """Resolves human app name to binary or executable alias."""
    clean_app = app_query.lower().strip().replace("the ", "")
    app_map = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "code": "code",
        "vscode": "code",
        "vs code": "code",
        "visual studio code": "code",
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "edge": "msedge.exe",
        "msedge": "msedge.exe",
        "brave": "brave.exe",
        "firefox": "firefox.exe",
        "paint": "mspaint.exe",
        "mspaint": "mspaint.exe",
        "wordpad": "wordpad.exe",
        "word": "winword.exe",
        "excel": "excel.exe",
        "powerpoint": "powerpnt.exe",
        "vlc": "vlc.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "spotify": "spotify:",
        "steam": "steam://",
        "discord": "discord:",
        "whatsapp": "whatsapp:",
        "telegram": "telegram:"
    }
    return app_map.get(clean_app, clean_app)



def open_file_in_app(file_query: str, app_query: str) -> str:
    """Finds a matching file/partial name and opens it inside the requested application."""
    file_path = find_file_by_name_or_partial(file_query)
    if not file_path:
        return f"Could not locate any file matching '{file_query}'."

    app_cmd = resolve_app_command(app_query)
    file_name = os.path.basename(file_path)

    try:
        subprocess.Popen(f'start "" {app_cmd} "{file_path}"', shell=True)
        return f"Opened '{file_name}' in {app_query}."
    except Exception as e:
        try:
            os.startfile(file_path)
            return f"Opened '{file_name}' (fallback to default program)."
        except Exception as ex:
            return f"Could not open '{file_name}': {ex}"


class SystemController:
    @staticmethod
    def open_website(site: str, browser: str = "default") -> str:
        clean_site = site.lower().strip().replace("the ", "")
        
        # Format URL properly
        if clean_site.startswith("http://") or clean_site.startswith("https://"):
            url = clean_site
        elif "." in clean_site:
            url = f"https://{clean_site}"
        elif clean_site in ["yt", "youtube"]:
            url = "https://www.youtube.com"
        elif clean_site in ["google"]:
            url = "https://www.google.com"
        elif clean_site in ["github"]:
            url = "https://www.github.com"
        elif clean_site in ["chatgpt"]:
            url = "https://chatgpt.com"
        elif clean_site in ["reddit"]:
            url = "https://www.reddit.com"
        elif clean_site in ["netflix"]:
            url = "https://www.netflix.com"
        else:
            url = f"https://www.google.com/search?q={clean_site}"

        b_key = browser.lower().strip()
        print(f"[EXECUTING]: Opening URL '{url}' in browser '{b_key}'")

        browser_executables = {
            "brave": "brave.exe",
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "firefox": "firefox.exe"
        }

        if b_key in browser_executables:
            target_exe = browser_executables[b_key]
            try:
                subprocess.Popen(f'start "" {target_exe} "{url}"', shell=True)
                return f"Opening {site} in {browser.title()}."
            except Exception as e:
                print(f"[Browser Fail]: {e}")
                webbrowser.open(url)
                return f"Opened {site} in default browser."
        else:
            webbrowser.open(url)
            return f"Opening {site} in your default browser."

    @staticmethod
    def launch_application(app_name: str) -> str:
        raw_cmd = app_name.lower().strip()
        for prefix in ["open ", "launch ", "start ", "run "]:
            if raw_cmd.startswith(prefix):
                raw_cmd = raw_cmd[len(prefix):].strip()

        # Handle 'open X in Y' or 'open X with Y'
        if " in " in raw_cmd:
            parts = raw_cmd.split(" in ", 1)
            return open_file_in_app(parts[0].strip(), parts[1].strip())
        elif " with " in raw_cmd:
            parts = raw_cmd.split(" with ", 1)
            return open_file_in_app(parts[0].strip(), parts[1].strip())

        clean = raw_cmd.replace("the ", "").strip()
        print(f"[EXECUTING]: Launching application or file '{clean}'")

        system_apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "task manager": "taskmgr.exe",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "settings": "ms-settings:",
            "explorer": "explorer.exe",
            "spotify": "spotify:",
            "steam": "steam://",
            "discord": "discord:",
            "whatsapp": "whatsapp:",
            "telegram": "telegram:",
            "vlc": "vlc.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "code": "code",
            "vscode": "code",
            "vs code": "code",
            "paint": "mspaint.exe"
        }


        # 1. Try Windows native registered commands / URIs
        if clean in system_apps:
            try:
                os.startfile(system_apps[clean])
                return f"Launched {app_name}."
            except Exception as e:
                print(f"[Launch Error]: {e}")

        # 2. Search for exact or partial file matches across any extension
        file_path = find_file_by_name_or_partial(clean)
        if file_path:
            try:
                os.startfile(file_path)
                return f"Opened file '{os.path.basename(file_path)}'."
            except Exception as e:
                print(f"[File Start Error]: {e}")

        # 3. Try direct execution through shell
        try:
            os.startfile(clean)
            return f"Launched {app_name}."
        except Exception:
            cmd = f'powershell -Command "Start-Process \'{clean}\'"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                return f"Launched {app_name} via Windows Shell."
            return f"Could not find an executable, application, or file matching '{app_name}'."


if __name__ == "__main__":
    print("Running Sanity Test on SystemController...")
    print(SystemController.launch_application("notepad"))
    print(SystemController.open_website("youtube", "edge"))

