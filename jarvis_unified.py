import os
import io
import sys
import time
import subprocess
import webbrowser
import numpy as np
import pyaudio
import psutil
from scipy import signal
import shutil
import json
import ollama

try:
    from jarvis_banner import print_jarvis_banner
    print_jarvis_banner()
except Exception:
    pass


try:
    from AppOpener import open as open_app
except ImportError:
    open_app = None

from faster_whisper import WhisperModel
import openwakeword
from openwakeword.model import Model

# Windows Mutex lock (Prevents multiple instances)
import tempfile
import atexit

LOCK_FILE = os.path.join(tempfile.gettempdir(), "jarvis_active_assistant.lock")

try:
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
except Exception:
    pass

@atexit.register
def _cleanup_lock_file():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass

# Set standard stdout encoding to UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ==========================================
# 1. HARDWARE & MODEL INITIALIZATION
# ==========================================
p = pyaudio.PyAudio()

# Auto-detect native hardware sample rate from sound card
try:
    default_dev = p.get_default_input_device_info()
    native_hardware_rate = int(default_dev.get('defaultSampleRate', 48000))
except Exception:
    native_hardware_rate = 48000

# Change this to your real mic index if needed (or set env var JARVIS_MIC_INDEX)
env_mic = os.getenv("JARVIS_MIC_INDEX")
MIC_INDEX = int(env_mic) if env_mic is not None and env_mic.strip() != "" else None

MIC_RATE = int(os.getenv("JARVIS_MIC_RATE", str(native_hardware_rate)))
TARGET_RATE = 16000
CHUNK = int(1280 * (MIC_RATE / TARGET_RATE))
WAKE_THRESHOLD = float(os.getenv("JARVIS_WAKE_THRESHOLD", "0.1"))

try:
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=MIC_RATE,
        input=True,
        input_device_index=MIC_INDEX,
        frames_per_buffer=CHUNK
    )
except Exception as e:
    print(f"⚠️ Failed to open audio stream at {MIC_RATE} Hz: {e}")
    if MIC_RATE != 48000:
        print("Retrying with 48000 Hz native sample rate...")
        MIC_RATE = 48000
        CHUNK = int(1280 * (MIC_RATE / TARGET_RATE))
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=MIC_RATE,
            input=True,
            input_device_index=MIC_INDEX,
            frames_per_buffer=CHUNK
        )


import urllib.request

def ensure_ollama_service_running():
    """Checks if local Ollama server is responding on port 11434; launches 'ollama serve' if down."""
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.5)
    except Exception:
        print("⚡ [Ollama Auto-Start]: Service not active. Launching 'ollama serve'...")
        try:
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            subprocess.Popen("ollama serve", shell=True, creationflags=creationflags)
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ [Ollama Service Error]: {e}")

def get_available_ollama_model():
    """Auto-detects installed models in local Ollama instance."""
    ensure_ollama_service_running()
    try:
        models_res = ollama.list()
        model_list = models_res.get('models', []) if isinstance(models_res, dict) else getattr(models_res, 'models', [])
        names = []
        for m in model_list:
            if isinstance(m, dict):
                names.append(m.get('name', ''))
            elif hasattr(m, 'model'):
                names.append(getattr(m, 'model', ''))
            elif hasattr(m, 'name'):
                names.append(getattr(m, 'name', ''))

        env_model = os.getenv("OLLAMA_MODEL")
        if env_model and any(env_model in n for n in names):
            return env_model

        for preferred in ["qwen2.5:3b", "llama3.1:8b", "llama3.2", "qwen2.5"]:
            for name in names:
                if preferred in name:
                    return name

        if names:
            return names[0]
    except Exception:
        pass
    return "qwen2.5:3b"

OLLAMA_MODEL = get_available_ollama_model()
print(f"Active Local LLM Model: {OLLAMA_MODEL}")

print("⏳ Initializing local neural engines...")

# 1. Local Wake Word Engine
try:
    openwakeword.utils.download_models()
except Exception:
    pass
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

# 2. Local Whisper STT (Runs offline on CPU/GPU)
print("Loading Whisper STT model...")
stt_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

# ==========================================
# 2. SYSTEM CONTROL TOOLS
# ==========================================

def open_website(site: str, browser: str = "default") -> str:
    """Opens a website or link in a designated web browser (brave, edge, default)."""
    clean_site = site.lower().strip().replace(" ", "")
    shortcuts = {
        "yt": "https://www.youtube.com",
        "youtube": "https://www.youtube.com",
        "github": "https://www.github.com",
        "google": "https://www.google.com",
        "reddit": "https://www.reddit.com",
        "chatgpt": "https://chatgpt.com"
    }
    url = shortcuts.get(clean_site, clean_site if clean_site.startswith("http") else f"https://{clean_site}.com" if "." in clean_site else f"https://www.google.com/search?q={clean_site}")
    
    b_map = {
        "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    }
    b_key = browser.lower().strip()
    
    for k, exe_path in b_map.items():
        if (k in b_key or b_key in k) and os.path.exists(exe_path):
            try:
                subprocess.Popen([exe_path, url])
                return f"Opened {site} in {k.title()}."
            except Exception:
                pass

    try:
        webbrowser.open(url)
        return f"Opened {site} in default browser."
    except Exception as e:
        return f"Could not open {site}: {e}"

def launch_application(app_name: str) -> str:
    # 1. Normalize the transcription (handles 'note pad', 'CALCULATOR', 'the notepad')
    raw = app_name.lower().replace("the ", "").replace("app", "").replace("application", "").strip()
    compressed = raw.replace(" ", "")

    print(f"\n[DEBUG] Raw app received: '{app_name}' | Normalized: '{compressed}'")

    # 2. Hardcoded absolute Windows commands/protocols
    system_targets = {
        "notepad": "notepad.exe",
        "calc": "calc.exe",
        "calculator": "calc.exe",
        "taskmgr": "taskmgr.exe",
        "taskmanager": "taskmgr.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "explorer": "explorer.exe",
        "fileexplorer": "explorer.exe",
        "settings": "ms-settings:",
        "paint": "mspaint.exe",
        "chrome": "chrome.exe",
        "brave": "brave.exe",
        "edge": "msedge.exe"
    }

    target = system_targets.get(compressed, system_targets.get(raw, None))

    # Priority A: Launch direct Windows system executable
    if target:
        try:
            # os.startfile handles URLs, protocols, and standard Windows EXEs directly
            os.startfile(target)
            return f"Successfully opened {target}."
        except Exception as e:
            print(f"[DEBUG] os.startfile failed on {target}: {e}")

    # Priority B: Resolve executable path from system PATH
    exe_path = shutil.which(f"{compressed}.exe") or shutil.which(f"{raw}.exe")
    if exe_path:
        try:
            subprocess.Popen([exe_path], shell=False)
            return f"Successfully started {exe_path}."
        except Exception as e:
            print(f"[DEBUG] Subprocess failed on {exe_path}: {e}")

    # Priority C: Direct Windows Shell Start command
    try:
        command_to_run = target if target else raw
        subprocess.Popen(f'start "" "{command_to_run}"', shell=True)
        return f"Dispatched start signal for {command_to_run}."
    except Exception as e:
        print(f"[DEBUG] Shell start failed: {e}")

    # Priority D: PowerShell fallback
    try:
        run_cmd = f"powershell -Command \"Start-Process '{compressed}'\""
        result = subprocess.run(run_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return f"Launched {compressed} via PowerShell."
        else:
            print(f"[DEBUG] PowerShell Error: {result.stderr.strip()}")
    except Exception as e:
        print(f"[DEBUG] PowerShell execution failed: {e}")

    return f"Failed to open '{app_name}'. Target executable not found."




def terminate_process(process_name: str) -> str:
    """Kills an active Windows process by name."""
    target = process_name.lower().replace(".exe", "").strip()
    killed = []
    for proc in psutil.process_iter(['name']):
        try:
            if target in proc.info['name'].lower():
                proc.kill()
                killed.append(proc.info['name'])
        except Exception:
            continue
    return f"Terminated {', '.join(set(killed))}." if killed else f"No process named {process_name} found."

TOOLS_LIST = [open_website, launch_application, terminate_process]
AVAILABLE_FUNCS = {
    "open_website": open_website,
    "launch_application": launch_application,
    "terminate_process": terminate_process
}

# ==========================================
# 3. AUDIO CAPTURE & DISPATCH PIPELINE
# ==========================================
def resample_audio(audio_np, orig_sr, target_sr=16000):
    if orig_sr == target_sr:
        return audio_np
    orig_len = len(audio_np)
    target_len = int(orig_len * target_sr / orig_sr)
    x_orig = np.linspace(0, 1, orig_len)
    x_target = np.linspace(0, 1, target_len)
    return np.interp(x_target, x_orig, audio_np.astype(np.float32)).astype(np.int16)

def record_user_command(silence_limit_seconds=2.5, max_record_seconds=35.0) -> bytes:
    """Listens until user stops speaking, returning raw 16kHz audio."""
    print("🎙️  LISTENING NOW — Speak your command (e.g. 'Open Notepad')...")
    sys.stdout.flush()

    # Flush trailing hardware buffer before recording starts
    try:
        while stream.get_read_available() > 0:
            stream.read(stream.get_read_available(), exception_on_overflow=False)
    except Exception:
        pass

    frames = []
    silent_chunks = 0
    speech_started = False
    chunks_per_sec = TARGET_RATE / 1280.0
    max_silent_chunks = int(chunks_per_sec * silence_limit_seconds)
    total_chunks = int(chunks_per_sec * max_record_seconds)

    for _ in range(total_chunks):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frame_np = np.frombuffer(data, dtype=np.int16)

        if MIC_RATE != TARGET_RATE:
            frame_downsampled = resample_audio(frame_np, MIC_RATE, TARGET_RATE)
            frames.append(frame_downsampled.tobytes())
            rms = np.sqrt(np.mean(frame_downsampled.astype(np.float32) ** 2))
        else:
            frames.append(data)
            rms = np.sqrt(np.mean(frame_np.astype(np.float32) ** 2))

        if rms > 75:
            speech_started = True

        if rms < 55:
            silent_chunks += 1
            if speech_started and silent_chunks > max_silent_chunks:
                break
        else:
            silent_chunks = 0

    print("⏳ Processing voice command...")
    return b"".join(frames)



def transcribe_offline(audio_bytes: bytes) -> str:
    """Runs local Faster-Whisper on the captured PCM buffer."""
    if len(audio_bytes) < TARGET_RATE * 0.8 * 2:
        return ""
    
    # Normalize int16 PCM to float32
    audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    segments, _ = stt_model.transcribe(audio_data, vad_filter=True)
    text = " ".join([seg.text for seg in segments]).strip()
    return text

def speak_out_loud(text: str):
    """Speaks out loud through Windows speakers."""
    clean_text = text.strip()
    if not clean_text:
        return

    print(f"\nJ.A.R.V.I.S.: {clean_text}\n")
    sys.stdout.flush()

    # 1. Native Windows SAPI5 Speech Engine (win32com)
    try:
        import win32com.client
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak(clean_text)
        return
    except Exception:
        pass

    # 2. Pyttsx3 TTS Fallback
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', 175)
        engine.say(clean_text)
        engine.runAndWait()
        return
    except Exception:
        pass

    # 3. PowerShell System.Speech Fallback
    try:
        escaped_text = clean_text.replace('"', "'")
        ps_speech = f'Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak("{escaped_text}")'
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_speech], capture_output=True, timeout=10)
    except Exception:
        pass

def fallback_action_dispatcher(user_command: str) -> str:
    """Guaranteed fallback launcher for desktop applications, websites, and processes."""
    cmd = user_command.lower().strip()

    # 1. Apps
    if any(k in cmd for k in ["notepad", "note pad"]):
        return launch_application("notepad")
    if any(k in cmd for k in ["calc", "calculator"]):
        return launch_application("calc")
    if any(k in cmd for k in ["cmd", "command prompt", "terminal"]):
        return launch_application("cmd")
    if any(k in cmd for k in ["task manager", "taskmgr"]):
        return launch_application("taskmgr")
    if any(k in cmd for k in ["explorer", "file explorer"]):
        return launch_application("explorer")
    if "settings" in cmd:
        return launch_application("settings")
    if "chrome" in cmd:
        return launch_application("chrome")
    if "brave" in cmd:
        return launch_application("brave")
    if "edge" in cmd:
        return launch_application("edge")

    # 2. Websites
    if any(k in cmd for k in ["youtube", "yt"]):
        return open_website("youtube")
    if "github" in cmd:
        return open_website("github")
    if "google" in cmd:
        return open_website("google")
    if "reddit" in cmd:
        return open_website("reddit")

    # 3. Process Termination
    if any(k in cmd for k in ["close", "kill", "stop", "terminate"]):
        for proc in ["chrome", "edge", "brave", "firefox", "notepad", "spotify", "calc"]:
            if proc in cmd:
                return terminate_process(proc)

    return None

def execute_with_ollama(command: str):
    """Passes spoken text to local Ollama with tools and speaks the response."""
    print(f"\n🗣️ You Said: \"{command}\"")

    try:
        ensure_ollama_service_running()
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are J.A.R.V.I.S. Use available tools when the user requests an action on apps, websites, or processes."
                },
                {"role": "user", "content": command}
            ],
            tools=TOOLS_LIST
        )
        msg = response.message

        if msg.tool_calls:
            for tool in msg.tool_calls:
                fn_name = tool.function.name
                fn_args = tool.function.arguments

                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}

                print(f"⚙️ [Action]: {fn_name}({fn_args})")
                if fn_name in AVAILABLE_FUNCS:
                    output = AVAILABLE_FUNCS[fn_name](**fn_args)
                    speak_out_loud(output)
                else:
                    speak_out_loud(f"Command {fn_name} is not recognized.")
        else:
            fallback_res = fallback_action_dispatcher(command)
            if fallback_res:
                speak_out_loud(fallback_res)
            elif msg.content:
                speak_out_loud(msg.content)

    except Exception as e:
        print(f"❌ [Ollama Error]: {e}")
        fallback_res = fallback_action_dispatcher(command)
        if fallback_res:
            reply = f"Right away, Sir. {fallback_res}"
            speak_out_loud(reply)
        else:
            speak_out_loud(f"I encountered an issue executing your command, sir.")



# ==========================================
# 4. MAIN BACKGROUND LISTENER LOOP
# ==========================================
def run_main_loop():
    print("\n=======================================================")
    print(" 🤖 J.A.R.V.I.S. LISTENING ENGINE ONLINE")
    print(" Say 'Hey Jarvis' to wake the assistant...")
    print("=======================================================\n")

    while True:
        try:
            # 1. Read standard audio slice
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_frame = np.frombuffer(data, dtype=np.int16)

            if MIC_RATE != TARGET_RATE:
                audio_frame = resample_audio(audio_frame, MIC_RATE, TARGET_RATE)

            # 2. Run prediction
            prediction = oww_model.predict(audio_frame)
            score = prediction.get("hey_jarvis", 0.0)

            if score >= WAKE_THRESHOLD:
                print(f"\n⚡ [WAKE DETECTED] Score: {score:.3f}")
                
                # Audible feedback
                try:
                    import winsound
                    winsound.Beep(1200, 150)
                except Exception:
                    pass

                # Reset openWakeWord memory immediately
                oww_model.reset()

                # Record user speech
                audio_buffer = record_user_command()
                command_text = transcribe_offline(audio_buffer)

                if command_text:
                    execute_with_ollama(command_text)
                else:
                    print("⚠️ No intelligible speech detected.")

                print("\nListening for 'Hey Jarvis'...")

                # 3. CRITICAL: Flush trailing audio to clear out the previous turn
                oww_model.reset()
                for _ in range(int(MIC_RATE / CHUNK * 0.8)):
                    try:
                        stream.read(CHUNK, exception_on_overflow=False)
                    except Exception:
                        pass

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Loop Error]: {e}")
            oww_model.reset()
            time.sleep(0.5)

    stream.stop_stream()
    stream.close()
    p.terminate()

if __name__ == "__main__":
    if "--auto-listen" in sys.argv:
        print("\n=======================================================")
        print(" 🤖 J.A.R.V.I.S. ACTIVE — LISTENING FOR YOUR COMMAND...")
        print("=======================================================\n")

        try:
            import winsound
            winsound.Beep(1000, 100)
            winsound.Beep(1200, 150)
        except Exception:
            pass

        audio_buffer = record_user_command()
        command_text = transcribe_offline(audio_buffer)

        if command_text:
            execute_with_ollama(command_text)
        else:
            speak_out_loud("I didn't catch that, Sir. Say 'Hey Jarvis' to try again.")

        run_main_loop()
    else:
        run_main_loop()



