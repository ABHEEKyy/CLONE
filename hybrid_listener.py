import os
import sys
import time
import subprocess
import numpy as np
import pyaudio
import psutil
from scipy import signal
import openwakeword
from openwakeword.model import Model

# Safely handle stdio when running as a hidden background daemon (VBScript/pythonw)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Cooldown state variables
COOLDOWN_SECONDS = 12.0
last_activation_timestamp = 0.0
CURRENT_PID = os.getpid()


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CMD_SCRIPT = os.path.join(PROJECT_DIR, "jarvis_voice_assistant.py")

import tempfile

LOCK_FILE = os.path.join(tempfile.gettempdir(), "jarvis_active_assistant.lock")

def is_jarvis_running() -> bool:
    """Checks PID lockfile & Task Manager for an active Jarvis instance, ignoring this listener."""
    # 1. Deterministic PID Lockfile check
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                pid_str = f.read().strip()
                if pid_str.isdigit():
                    pid = int(pid_str)
                    if pid != CURRENT_PID and psutil.pid_exists(pid):
                        try:
                            p = psutil.Process(pid)
                            if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                                return True
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            return True
        except Exception:
            pass

    # 2. Fallback process iteration check
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] == CURRENT_PID:
                continue

            cmdline = " ".join(proc.info.get('cmdline') or []).lower()
            if any(s in cmdline for s in ["jarvis_voice_assistant.py", "jarvis_unified.py", "jarvis_ollama.py", "jarvis_wake_controller.py"]):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def flush_audio_buffer(stream):
    """Purges ALL unread audio frames from the PyAudio hardware input queue."""
    try:
        avail = stream.get_read_available()
        if avail > 0:
            stream.read(avail, exception_on_overflow=False)
    except Exception:
        pass

def resample_audio(audio_np, orig_sr, target_sr=16000):
    if orig_sr == target_sr:
        return audio_np
    orig_len = len(audio_np)
    target_len = int(orig_len * target_sr / orig_sr)
    x_orig = np.linspace(0, 1, orig_len)
    x_target = np.linspace(0, 1, target_len)
    return np.interp(x_target, x_orig, audio_np.astype(np.float32)).astype(np.int16)

try:
    openwakeword.utils.download_models()
except Exception:
    pass
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

p = pyaudio.PyAudio()

# Auto-detect native hardware sample rate from sound card
try:
    default_dev = p.get_default_input_device_info()
    native_hardware_rate = int(default_dev.get('defaultSampleRate', 48000))
except Exception:
    native_hardware_rate = 48000

# Change this to your real mic index from Step 1 if needed (or set env var JARVIS_MIC_INDEX)
env_mic = os.getenv("JARVIS_MIC_INDEX")
MIC_INDEX = int(env_mic) if env_mic is not None and env_mic.strip() != "" else None

MIC_RATE = int(os.getenv("JARVIS_MIC_RATE", str(native_hardware_rate)))
TARGET_RATE = 16000
CHUNK = int(1280 * (MIC_RATE / TARGET_RATE))
WAKE_THRESHOLD = float(os.getenv("JARVIS_WAKE_THRESHOLD", "0.5"))

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


print("=" * 60)
print(f"⚡ Background Wake Daemon Online (Mic Index: {MIC_INDEX}, Native Rate: {MIC_RATE} Hz)")
print("   Waiting for 'Hey Jarvis'...")
print("=" * 60)

while True:
    try:
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_frame = np.frombuffer(data, dtype=np.int16)

        # Time-domain linear interpolation resampling for pristine openWakeWord audio
        if MIC_RATE != TARGET_RATE:
            audio_frame = resample_audio(audio_frame, MIC_RATE, TARGET_RATE)

        # Print raw volume for diagnostics
        rms = np.sqrt(np.mean(audio_frame.astype(np.float32) ** 2))
        prediction = oww_model.predict(audio_frame)
        score = prediction.get("hey_jarvis", 0.0)

        if rms > 80:
            print(f"Mic Live (RMS: {int(rms):<5}) | Hey Jarvis Score: {score:.3f}")


        if score >= WAKE_THRESHOLD:
            now = time.time()

            # Guard 1: Temporal Cooldown
            if now - last_activation_timestamp < COOLDOWN_SECONDS:
                oww_model.reset()
                flush_audio_buffer(stream)
                continue

            # Guard 2: Process Existence Check
            if is_jarvis_running():
                print("⚡ [Ignored] J.A.R.V.I.S. is already active on your desktop.")
                last_activation_timestamp = now
                oww_model.reset()
                flush_audio_buffer(stream)
                continue

            # Clean Trigger
            print(f"\n🚀 Wake word detected ({score:.2f})! Popping open J.A.R.V.I.S...")
            last_activation_timestamp = time.time()

            # Reset internal ONNX feature weights & purge hardware audio buffer
            oww_model.reset()
            flush_audio_buffer(stream)

            # Launch visible CMD window running assistant
            clean_proj = PROJECT_DIR.replace('"', '')
            clean_script = CMD_SCRIPT.replace('"', '')
            launch_cmd = f'cmd /c start "J.A.R.V.I.S. Console" cmd /k "cd /d {clean_proj} && py -u {clean_script} --auto-listen"'
            subprocess.Popen(launch_cmd, shell=True)

            # Pause background listener while active assistant handles the mic & command
            time.sleep(10)
            oww_model.reset()
            flush_audio_buffer(stream)
            last_activation_timestamp = time.time()
            print("Listening resumed.\n")

    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"[Listener Exception]: {e}")

stream.stop_stream()
stream.close()
p.terminate()





