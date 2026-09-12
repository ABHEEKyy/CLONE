import json
import os
import re
import subprocess
import sys
import time
import webbrowser
import psutil
import pyttsx3
import speech_recognition as sr
from dotenv import load_dotenv
from openai import OpenAI

# Load configuration from .env file
load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
TTS_RATE = int(os.getenv("TTS_VOICE_RATE", "170"))

# Set standard stdout encoding to UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Initialize pyttsx3 as secondary TTS fallback
engine = None
try:
    engine = pyttsx3.init()
    engine.setProperty('rate', TTS_RATE)
    engine.setProperty('volume', 1.0)
except Exception:
    engine = None


def speak(text: str):
    """Speaks out loud through Windows speakers for EVERY single response."""
    clean_text = text.strip()
    if not clean_text:
        return

    print(f"\nJ.A.R.V.I.S.: {clean_text}\n")
    sys.stdout.flush()

    if os.environ.get("HEADLESS_TEST") != "1":
        spoken = False
        # 1. Native Windows SAPI5 Speech Engine (win32com)
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(clean_text)
            spoken = True
        except Exception:
            pass

        # 2. Pyttsx3 TTS Engine Fallback
        if not spoken and engine:
            try:
                engine.say(clean_text)
                engine.runAndWait()
                spoken = True
            except Exception:
                pass

        # 3. PowerShell System.Speech Fallback
        if not spoken:
            try:
                escaped_text = clean_text.replace('"', "'")
                ps_speech = f'Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak("{escaped_text}")'
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_speech], capture_output=True, timeout=10)
            except Exception:
                pass


# Initialize OpenAI client pointing to local Ollama API
client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama"
)


from win_tools_fixed import SystemController


def ensure_ollama_service_running():
    """Checks if local Ollama server is responding on port 11434; launches 'ollama serve' if down."""
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/", timeout=2)
        return True
    except Exception:
        print("[Ollama Auto-Start]: Service not active. Launching 'ollama serve'...")
        try:
            subprocess.Popen("ollama serve", shell=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            time.sleep(3)
            return True
        except Exception as e:
            print(f"[Ollama Service Error]: {e}")
            return False


def ensure_tool_calling_model():
    """Verifies a native function-calling model exists in Ollama; pulls llama3.1:8b automatically if needed."""
    ensure_ollama_service_running()
    try:
        models = client.models.list()
        available_names = [m.id for m in models.data]
        for name in available_names:
            if any(k in name for k in ["llama3.1", "llama3.2", "qwen2.5", "mistral"]):
                return name
        print("[Ollama Auto-Pull]: No native tool-calling model found in local Ollama. Pulling llama3.1:8b...")
        subprocess.run(["ollama", "pull", "llama3.1:8b"], check=False)
        return "llama3.1:8b"
    except Exception as e:
        print(f"[Ollama Model Check]: {e}")
        return "llama3.1:8b"


def fallback_action_dispatcher(user_command: str) -> str:
    """Guaranteed Action Dispatcher: Ensures immediate execution on Windows desktop."""
    cmd = user_command.lower().strip()

    # 1. App Launching Intent
    app_map = {
        "notepad": "notepad",
        "calculator": "calc",
        "calc": "calc",
        "task manager": "task manager",
        "cmd": "cmd",
        "terminal": "terminal",
        "settings": "settings",
        "explorer": "explorer",
        "spotify": "spotify"
    }
    for app_key, app_val in app_map.items():
        if app_key in cmd:
            return SystemController.launch_application(app_val)

    # 2. Website Opening Intent
    if any(k in cmd for k in ["open", "launch", "go to", "visit"]):
        selected_browser = "default"
        for b in ["chrome", "edge", "brave", "firefox"]:
            if b in cmd:
                selected_browser = b
                break

        for site in ["youtube", "google", "github", "chatgpt", "reddit", "netflix"]:
            if site in cmd:
                return SystemController.open_website(site, selected_browser)

    # 3. Process Termination Intent
    if any(k in cmd for k in ["kill", "close", "terminate", "stop"]):
        for proc in ["chrome", "edge", "brave", "firefox", "notepad", "spotify", "calc"]:
            if proc in cmd:
                return SystemController.terminate_process(proc)

    # 4. PowerShell Execution Intent
    if "powershell" in cmd or "run command" in cmd:
        ps_cmd = cmd.replace("run powershell", "").replace("powershell", "").strip()
        if ps_cmd:
            return SystemController.run_powershell_command(ps_cmd)

    return None


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_powershell_command",
            "description": "Executes arbitrary PowerShell commands on Windows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The PowerShell command string to run"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Opens a website or link in a designated web browser (Chrome, Edge, Brave, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {"type": "string", "description": "Website name or domain, e.g. 'youtube', 'github.com'"},
                    "browser": {"type": "string", "enum": ["chrome", "edge", "brave", "firefox", "default"]}
                },
                "required": ["site"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "launch_application",
            "description": "Launches a Windows desktop program or tool (e.g. 'notepad', 'calc', 'task manager').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the app"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminate_process",
            "description": "Kills or stops a running process by name (e.g. 'chrome', 'spotify').",
            "parameters": {
                "type": "object",
                "properties": {
                    "process_name": {"type": "string", "description": "Name of the process to kill"}
                },
                "required": ["process_name"]
            }
        }
    }
]

SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S., an operating system voice controller running offline on the user's PC.\n"
    "MANDATORY INSTRUCTIONS:\n"
    "1. When the user asks to open an application, open a website, execute a PowerShell command, or close a process, "
    "you MUST call the matching tool function immediately.\n"
    "2. NEVER reply with conversational text saying 'I will open it' or 'Opening now' without calling a tool function.\n"
    "3. For desktop programs (like 'notepad', 'calc'), always call 'launch_application'."
)


def get_available_model():
    """Finds an available tool-capable model in local Ollama engine or auto-pulls llama3.1:8b."""
    return ensure_tool_calling_model()


def process_command(user_command: str):
    # Single-turn fresh context per command to eliminate line repetition bugs
    fresh_history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_command}
    ]
    active_model = get_available_model()

    print(f"\n[User Request]: {user_command}")

    try:
        response = client.chat.completions.create(
            model=active_model,
            messages=fresh_history,
            tools=TOOLS,
            tool_choice="auto"
        )
        msg = response.choices[0].message

        print(f"[DEBUG] Model: {active_model} | Tool Calls: {msg.tool_calls}")

        if msg.tool_calls:
            for tool in msg.tool_calls:
                f_name = tool.function.name
                args = json.loads(tool.function.arguments)
                print(f"[Executing Tool]: {f_name}({args})")

                if hasattr(SystemController, f_name):
                    output = getattr(SystemController, f_name)(**args)
                else:
                    output = "Action failed: tool not found."

                print(f"[Execution Result]: {output}")
                reply = f"{output}"
        else:
            print("⚠️ Invoking Guaranteed Action Dispatcher...")
            fallback_res = fallback_action_dispatcher(user_command)
            if fallback_res:
                reply = f"{fallback_res}"
            else:
                reply = msg.content

        speak(reply)

    except Exception as ex:
        print(f"Ollama Call Notice: {ex}")
        fallback_res = fallback_action_dispatcher(user_command)
        if fallback_res:
            speak(f"{fallback_res}")
        else:
            speak("I encountered an issue executing your command, sir.")


def listen_for_wake_word():
    raw_wakes = os.getenv("JARVIS_WAKE_WORDS", "hello jarvis,jarvis,hey jarvis,hi jarvis,wake up")
    wake_words = [w.strip().lower() for w in raw_wakes.split(",")]

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    print("\n" + "=" * 60)
    print("J.A.R.V.I.S. DESKTOP VOICE CONTROLLER ONLINE")
    print(f"Active Ollama Model: {get_available_model()}")
    print(f"Wake Words: {wake_words}")
    print("Say 'HELLO JARVIS' or 'JARVIS' to activate.")
    print("=" * 60 + "\n")

    print("J.A.R.V.I.S. is online, sir.")

    try:
        mic = sr.Microphone()
    except Exception as e:
        print(f"Microphone notice: {e}. Switching to text mode.")
        run_text_mode()
        return

    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
    except Exception as e:
        print(f"Microphone error: {e}. Switching to text mode.")
        run_text_mode()
        return

    while True:
        try:
            print("Listening for wake phrase ('hello jarvis' / 'jarvis')...")
            with mic as source:
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=6)

            try:
                speech = recognizer.recognize_google(audio).lower().strip()
                print(f"[Heard Voice]: '{speech}'")

                matched_wake = False
                command_remainder = ""

                for w in wake_words:
                    if w in speech:
                        matched_wake = True
                        command_remainder = speech.split(w, 1)[-1].strip()
                        break

                if matched_wake:
                    if command_remainder and len(command_remainder) > 2:
                        process_command(command_remainder)
                    else:
                        speak("Yes sir?")
                        # Allow speaker audio to finish before listening
                        time.sleep(0.3)
                        print("Waiting for your command...")
                        
                        start_time = time.time()
                        got_command = False

                        while (time.time() - start_time) < 30:
                            try:
                                remaining_time = int(30 - (time.time() - start_time))
                                if remaining_time <= 0:
                                    break
                                with mic as cmd_source:
                                    recognizer.adjust_for_ambient_noise(cmd_source, duration=0.2)
                                    cmd_audio = recognizer.listen(cmd_source, timeout=min(remaining_time, 8), phrase_time_limit=10)
                                cmd_text = recognizer.recognize_google(cmd_audio).lower().strip()
                                if cmd_text:
                                    print(f"[Spoken Command]: '{cmd_text}'")
                                    process_command(cmd_text)
                                    got_command = True
                                    break
                            except sr.UnknownValueError:
                                continue
                            except sr.WaitTimeoutError:
                                continue

                        if not got_command:
                            print("No command heard. Resetting to wake phrase listener...")

            except sr.UnknownValueError:
                pass
            except sr.RequestError:
                pass

        except sr.WaitTimeoutError:
            continue
        except (KeyboardInterrupt, EOFError):
            print("\nExiting J.A.R.V.I.S. Voice Listener.")
            break
        except Exception as ex:
            print(f"Listener loop notice: {ex}")


def run_text_mode():
    print("\nJ.A.R.V.I.S. Interactive Text Command Mode (Type any command)")
    while True:
        try:
            cmd = input("\nYou: ")
            if cmd.strip().lower() in ["exit", "quit"]:
                break
            if cmd.strip():
                process_command(cmd)
        except (KeyboardInterrupt, EOFError):
            break


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "voice"
    if mode == "text":
        run_text_mode()
    else:
        listen_for_wake_word()
