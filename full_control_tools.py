import os
import glob
import subprocess
import webbrowser
import psutil

class UniversalController:
    # Common browser executable paths on Windows
    @staticmethod
    def _get_browser_paths():
        local_app = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
        
        return {
            "brave": [
                rf"{prog_files}\BraveSoftware\Brave-Browser\Application\brave.exe",
                rf"{prog_files_x86}\BraveSoftware\Brave-Browser\Application\brave.exe",
                rf"{local_app}\BraveSoftware\Brave-Browser\Application\brave.exe",
            ],
            "chrome": [
                rf"{prog_files}\Google\Chrome\Application\chrome.exe",
                rf"{prog_files_x86}\Google\Chrome\Application\chrome.exe",
                rf"{local_app}\Google\Chrome\Application\chrome.exe",
            ],
            "edge": [
                rf"{prog_files_x86}\Microsoft\Edge\Application\msedge.exe",
                rf"{prog_files}\Microsoft\Edge\Application\msedge.exe",
            ],
            "firefox": [
                rf"{prog_files}\Mozilla Firefox\firefox.exe",
                rf"{prog_files_x86}\Mozilla Firefox\firefox.exe",
            ]
        }

    @classmethod
    def open_website(cls, site: str, browser: str = "default") -> str:
        """Opens any site or search query in the requested browser."""
        clean_site = site.lower().strip().replace(" ", "")
        
        # Build clean URL
        if clean_site.startswith("http://") or clean_site.startswith("https://"):
            url = site.strip()
        elif "." in clean_site:
            url = f"https://{clean_site}"
        else:
            url = f"https://www.google.com/search?q={site.strip()}"

        b_key = browser.lower().strip()
        browser_map = cls._get_browser_paths()

        # Check explicit browser execution
        if b_key in browser_map:
            for path in browser_map[b_key]:
                if os.path.exists(path):
                    try:
                        subprocess.Popen([path, url])
                        return f"Opened {site} in {browser.title()}."
                    except Exception:
                        break

        # Fallback to default browser
        webbrowser.open(url)
        return f"Opened {site} in your default browser."

    @staticmethod
    def open_file_or_folder(name: str) -> str:
        """Finds and opens a local file, document, video, or directory by exact or partial name across workspace and user folders."""
        raw = name.lower().strip()
        for prefix in ["open ", "launch ", "start ", "run ", "the ", "file ", "folder ", "script "]:
            if raw.startswith(prefix):
                raw = raw[len(prefix):].strip()

        if not raw:
            return "Please provide a valid file or folder name."

        clean_raw = raw.replace("_", " ").replace("-", " ")
        compressed = raw.replace(" ", "").replace("_", "").replace("-", "")

        user_home = os.path.expanduser("~")
        workspace_root = os.getcwd()
        search_dirs = [
            workspace_root,
            os.path.abspath(os.path.join(workspace_root, "..")),
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, r"OneDrive\Desktop"),
            r"C:\Users\Public\Desktop",
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
                        clean_item_base = base_name.replace("_", " ").replace("-", " ").strip()
                        item_compressed = clean_item_base.replace(" ", "")

                        score = 0
                        if raw == item_lower or raw == base_name:
                            score = 100
                        elif clean_raw == clean_item_base:
                            score = 90
                        elif compressed == item_compressed:
                            score = 85
                        elif raw in item_lower or raw in base_name:
                            score = 75
                        elif clean_raw in clean_item_base:
                            score = 70
                        elif compressed in item_compressed:
                            score = 65
                        else:
                            words = [w for w in clean_raw.split() if len(w) > 1]
                            if words and all(w in clean_item_base for w in words):
                                score = 60

                        if score > 0:
                            seen.add(full_path)
                            matches.append((score, full_path))

                    if root.count(os.sep) - s_dir.count(os.sep) >= 3:
                        del dirs[:]
            except Exception:
                continue

        if matches:
            matches.sort(key=lambda x: x[0], reverse=True)
            chosen_path = matches[0][1]
            try:
                os.startfile(chosen_path)
                return f"Opened: {chosen_path}"
            except Exception as e:
                return f"Found '{os.path.basename(chosen_path)}' but failed to open: {e}"

        return f"Could not find any file or folder matching '{name}' in your system."

    @classmethod
    def open_file_in_app(cls, file_query: str, app_query: str) -> str:
        """Finds a file by full/partial name and launches it in the specified application."""
        user_home = os.path.expanduser("~")
        workspace_root = os.getcwd()
        search_dirs = [
            workspace_root,
            os.path.abspath(os.path.join(workspace_root, "..")),
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, r"OneDrive\Desktop"),
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Documents"),
            os.path.join(user_home, r"OneDrive\Documents"),
            user_home,
        ]
        
        clean_file = file_query.lower().strip()
        matched_path = None

        for sdir in search_dirs:
            if not os.path.exists(sdir):
                continue
            for root, dirs, files in os.walk(sdir):
                for item in files + dirs:
                    if clean_file in item.lower() or clean_file.replace(" ", "") in item.lower().replace(" ", "").replace("_", ""):
                        matched_path = os.path.abspath(os.path.join(root, item))
                        break
                if matched_path:
                    break
            if matched_path:
                break

        if not matched_path:
            return f"Could not find any file matching '{file_query}'."

        clean_app = app_query.lower().strip().replace("the ", "")
        system_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "code": "code",
            "vscode": "code",
            "vs code": "code",
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "brave": "brave.exe",
            "firefox": "firefox.exe",
            "paint": "mspaint.exe"
        }
        app_exe = system_map.get(clean_app, clean_app)

        try:
            subprocess.Popen(f'start "" {app_exe} "{matched_path}"', shell=True)
            return f"Opened '{os.path.basename(matched_path)}' in {app_query}."
        except Exception as e:
            os.startfile(matched_path)
            return f"Opened '{os.path.basename(matched_path)}' with default app."

    @classmethod
    def launch_application(cls, app_name: str) -> str:
        """Launches any Windows executable, shortcut, file, or Store application dynamically."""
        raw_cmd = app_name.lower().strip()
        for prefix in ["open ", "run ", "launch ", "execute ", "start "]:
            if raw_cmd.startswith(prefix):
                raw_cmd = raw_cmd[len(prefix):].strip()

        if " in " in raw_cmd:
            parts = raw_cmd.split(" in ", 1)
            return cls.open_file_in_app(parts[0].strip(), parts[1].strip())
        elif " with " in raw_cmd:
            parts = raw_cmd.split(" with ", 1)
            return cls.open_file_in_app(parts[0].strip(), parts[1].strip())

        clean = raw_cmd.replace("the ", "").strip()
        
        system_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "task manager": "taskmgr.exe",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "settings": "ms-settings:",
            "explorer": "explorer.exe",
            "spotify": "spotify:",
            "code": "code",
            "vs code": "code",
            "vscode": "code",
            "paint": "mspaint.exe",
            "wordpad": "wordpad.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "steam": "steam://",
            "discord": "discord:"
        }

        if clean in system_map:
            try:
                os.startfile(system_map[clean])
                return f"Launched {app_name}."
            except Exception:
                pass

        # Try partial file/folder lookup before generic fallback
        res = cls.open_file_or_folder(clean)
        if "Opened" in res:
            return res

        for target in [clean, f"{clean}.exe"]:
            try:
                os.startfile(target)
                return f"Launched {app_name}."
            except Exception:
                pass

        user_appdata = os.environ.get("APPDATA", "")
        program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
        start_menu_dirs = [
            rf"{user_appdata}\Microsoft\Windows\Start Menu\Programs",
            rf"{program_data}\Microsoft\Windows\Start Menu\Programs"
        ]

        for s_dir in start_menu_dirs:
            if not os.path.exists(s_dir):
                continue
            for root, _, files in os.walk(s_dir):
                for f in files:
                    if f.lower().endswith(".lnk") and clean in f.lower():
                        lnk_path = os.path.join(root, f)
                        try:
                            os.startfile(lnk_path)
                            return f"Launched {app_name} via Windows Start Menu."
                        except Exception:
                            pass

        cmd = f'powershell -Command "Start-Process \'{clean}\'"'
        res_cmd = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res_cmd.returncode == 0:
            return f"Launched {app_name} via Windows Shell."

        return f"Unable to locate or launch application or file matching '{app_name}'."

