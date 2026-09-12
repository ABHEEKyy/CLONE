"""Background listener daemon that waits for 'Hey Jarvis' to activate the floating Siri bubble.
Instead of opening a CMD terminal window, it opens a sleek Siri-like HUD bubble in the top corner of the screen.
"""

import os
import sys
import socket
import subprocess
import time
import numpy as np
import pyaudio
import openwakeword
from openwakeword.model import Model

import tempfile
import psutil

LOCK_FILE = os.path.join(tempfile.gettempdir(), "jarvis_active_assistant.lock")

def is_jarvis_running() -> bool:
    """Checks if an active Jarvis instance is already running."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                pid_str = f.read().strip()
                if pid_str.isdigit() and psutil.pid_exists(int(pid_str)):
                    return True
        except Exception:
            pass

    curr_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] == curr_pid:
                continue
            cmdline = " ".join(proc.info.get('cmdline') or []).lower()
            if any(s in cmdline for s in ["jarvis_voice_assistant.py", "jarvis_unified.py", "jarvis_ollama.py", "jarvis_wake_controller.py"]):
                return True
        except Exception:
            continue
    return False

def trigger_jarvis_bubble():
    """Launches J.A.R.V.I.S. in CMD terminal via Run_Jarvis.bat if not active."""
    if is_jarvis_running():
        print("⚡ [Daemon Ignored] J.A.R.V.I.S. is already active.", flush=True)
        return

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    bat_path = os.path.join(repo_root, "Run_Jarvis.bat")

    try:
        print(f">> [Opening CMD Terminal Controller]: {bat_path}", flush=True)
        subprocess.Popen(f'start "J.A.R.V.I.S." "{bat_path}"', shell=True)
    except Exception as e:
        print(f"[CMD Launch Error]: {e}", flush=True)



def listen_for_hey_jarvis():
    openwakeword.utils.download_models()
    models_to_load = ["hey_jarvis"]
    for path in openwakeword.get_pretrained_model_paths():
        if "jarvis" in os.path.basename(path).lower() and os.path.basename(path) not in models_to_load:
            models_to_load.append(path)

    model = Model(wakeword_models=models_to_load)
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=FRAME_SAMPLES,
    )

    print("\n==========================================", flush=True)
    print("Background Daemon Listening for 'Hey Jarvis'...")
    print("Wake word will open the Siri-style HUD bubble in the top corner!", flush=True)
    print("==========================================\n", flush=True)

    try:
        while True:
            frame = stream.read(FRAME_SAMPLES, exception_on_overflow=False)
            prediction = model.predict(np.frombuffer(frame, dtype=np.int16))
            score = max([v for k, v in prediction.items() if "jarvis" in k.lower()], default=0.0)
            if score >= 0.50:
                print(f"\n>> ['Hey Jarvis' Detected! Activating Assistant...]", flush=True)
                import winsound
                winsound.Beep(880, 100)
                winsound.Beep(1320, 150)

                trigger_jarvis_bubble()

                if hasattr(model, "reset"):
                    model.reset()
                time.sleep(10)
                try:
                    avail = stream.get_read_available()
                    if avail > 0:
                        stream.read(avail, exception_on_overflow=False)
                except Exception:
                    pass
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


if __name__ == "__main__":
    listen_for_hey_jarvis()
