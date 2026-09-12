import sys
import os
import subprocess
import webbrowser
import psutil
import ollama
import json
import traceback
import speech_recognition as sr

# Windows Mutex lock (Prevents multiple instances)
if sys.platform == "win32":
    import win32event
    import win32api
    import winerror

    # Must remain a global variable so Python doesn't garbage-collect the handle
    MUTEX_HANDLE = win32event.CreateMutex(None, False, "Global\\JarvisSingleInstanceLock")

    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        print("❌ Another instance of J.A.R.V.I.S. is already running. Exiting.")
        sys.exit(0)






MODEL = "llama3.1:8b"

def open_website(site: str, browser: str = "default") -> str:
    clean_site = site.lower().strip()
    shortcuts = {
        "yt": "https://www.youtube.com",
        "youtube": "https://www.youtube.com",
        "github": "https://www.github.com",
        "google": "https://www.google.com",
        "reddit": "https://www.reddit.com"
    }
    url = shortcuts.get(clean_site, clean_site if clean_site.startswith("http") else f"https://{clean_site}.com" if "." in clean_site else f"https://www.google.com/search?q={clean_site}")
    
    b_key = browser.lower().strip()
    
    # Common Windows install locations for Brave, Chrome, and Edge
    browser_lookup = {
        "brave": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            "brave.exe"
        ],
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            "chrome.exe"
        ],
        "edge": ["msedge.exe"]
    }

    if b_key in browser_lookup:
        for path in browser_lookup[b_key]:
            try:
                # Direct execution without shell=True escaping pitfalls for URLs with & or query params
                if os.path.exists(path):
                    subprocess.Popen([path, url])
                else:
                    subprocess.Popen(f'start "" "{path}" "{url}"', shell=True)
                return f"Opening {site} on {browser.title()}."
            except Exception:
                continue

    # Fallback to standard default browser
    webbrowser.open(url)
    return f"Opening {site} in your default browser."

def launch_application(app_name: str) -> str:
    clean = app_name.lower().strip().replace("the ", "")
    
    system_map = {
        "notepad": "notepad.exe",
        "calc": "calc.exe",
        "calculator": "calc.exe",
        "task manager": "taskmgr.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "settings": "ms-settings:",
        "explorer": "explorer.exe"
    }

    # 1. Native Windows binaries/URIs
    if clean in system_map:
        try:
            os.startfile(system_map[clean])
            return f"Launched {clean}."
        except Exception:
            pass

    # 2. Windows Start-Process Fallback
    try:
        subprocess.Popen(f'powershell -Command "Start-Process \'{clean}\'"', shell=True)
        return f"Initiated {clean}."
    except Exception as e:
        return f"Could not launch {clean}: {e}"

def terminate_process(process_name: str) -> str:
    target = process_name.lower().replace(".exe", "").strip()
    killed = []
    for proc in psutil.process_iter(['name']):
        try:
            if target in proc.info['name'].lower():
                proc.kill()
                killed.append(proc.info['name'])
        except Exception:
            continue
    return f"Terminated: {', '.join(set(killed))}." if killed else f"No active process matching '{process_name}' found."

TOOLS_LIST = [open_website, launch_application, terminate_process]
AVAILABLE_FUNCS = {
    "open_website": open_website,
    "launch_application": launch_application,
    "terminate_process": terminate_process
}

def process_jarvis_turn(user_input: str):
    print(f"\n[Command Received]: \"{user_input}\"")

    try:
        # Single Ollama call with system instruction to prevent template failure
        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are J.A.R.V.I.S. Use tools whenever the user asks to launch an app, open a website, or terminate a process."
                },
                {"role": "user", "content": user_input}
            ],
            tools=TOOLS_LIST
        )

        msg = response.message

        # Handle Tool Calling Directly
        if msg.tool_calls:
            for tool in msg.tool_calls:
                fn_name = tool.function.name
                fn_args = tool.function.arguments

                # Ensure string arguments are parsed into a dictionary
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}

                print(f"⚙️ [Action Found]: {fn_name} with parameters: {fn_args}")

                if fn_name in AVAILABLE_FUNCS:
                    try:
                        result = AVAILABLE_FUNCS[fn_name](**fn_args)
                        print(f"J.A.R.V.I.S.: Right away, Sir. {result}")
                    except Exception as ex:
                        print(f"❌ [TOOL EXECUTION ERROR]: {ex}")
                        print("\n" + "="*20 + " REAL PYTHON TRACEBACK " + "="*20)
                        traceback.print_exc()
                        print("="*60 + "\n")
                else:
                    print(f"J.A.R.V.I.S.: Apologies, Sir. Tool '{fn_name}' is not recognized.")
        else:
            # Conversational answer (no tools required)
            print(f"J.A.R.V.I.S.: {msg.content}")

    except Exception:
        # Stop masking the error! Print full traceback
        print("\n" + "="*20 + " REAL PYTHON TRACEBACK " + "="*20)
        traceback.print_exc()
        print("="*60 + "\n")

def listen_voice_loop():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 200
    recognizer.dynamic_energy_threshold = False  # Prevent auto-scaling threshold above spoken voice level
    recognizer.pause_threshold = 0.5

    wake_words = ["hello jarvis", "hey jarvis", "hi jarvis", "jarvis"]


    try:
        mic = sr.Microphone()
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.8)
        print("\n" + "="*55)
        print("⚡ J.A.R.V.I.S. VOICE CONTROLLER ONLINE")
        print("Say 'HELLO JARVIS' or 'HEY JARVIS' followed by your command.")
        print("Example: 'Hello Jarvis open youtube on brave'")
        print("="*55 + "\n")
    except Exception as e:
        print(f"⚠️ [Microphone Error]: {e}")
        return False

    while True:
        try:
            print("👂 [Waiting for 'Hello Jarvis' wake phrase...]")
            with mic as source:
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=8)
            
            try:
                user_speech = recognizer.recognize_google(audio).strip()
                if user_speech:
                    speech_lower = user_speech.lower()
                    print(f"🗣️ [Heard Audio]: \"{user_speech}\"")

                    matched_wake = None
                    for w in wake_words:
                        if w in speech_lower:
                            matched_wake = w
                            break

                    if matched_wake:
                        # Extract command after the wake phrase if spoken in one sentence
                        command_part = speech_lower.split(matched_wake, 1)[-1].strip()
                        if command_part and len(command_part) > 2:
                            process_jarvis_turn(command_part)
                        else:
                            print("\nJ.A.R.V.I.S.: Yes, Sir? Listening for your command...")
                            with mic as cmd_source:
                                recognizer.adjust_for_ambient_noise(cmd_source, duration=0.3)
                                cmd_audio = recognizer.listen(cmd_source, timeout=6, phrase_time_limit=8)
                            cmd_speech = recognizer.recognize_google(cmd_audio).strip()
                            if cmd_speech:
                                print(f"🗣️ [Command Heard]: \"{cmd_speech}\"")
                                process_jarvis_turn(cmd_speech)

            except sr.UnknownValueError:
                pass
            except sr.RequestError as re:
                print(f"❌ [Speech Service Notice]: {re}")
                
        except sr.WaitTimeoutError:
            continue
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down J.A.R.V.I.S. voice controller.")
            break
        except Exception as ex:
            print(f"❌ [Voice Loop Error]: {ex}")

    return True

def run_text_fallback():
    print("\n[Text Fallback Mode Active]: Type your commands below:")
    while True:
        try:
            cmd = input("You > ")
            if cmd.strip().lower() in ["exit", "quit", "q"]:
                break
            if cmd.strip():
                process_jarvis_turn(cmd)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    print("=====================================================")
    print("      J.A.R.V.I.S. PURE OLLAMA VOICE CONTROLLER      ")
    print("      (Zero Cloud APIs | 100% Local Execution)       ")
    print("=====================================================")
    
    success = listen_voice_loop()
    if not success:
        run_text_fallback()




