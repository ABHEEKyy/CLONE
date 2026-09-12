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

# Set standard stdout encoding to UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

MIC_RATE = int(os.getenv("JARVIS_MIC_RATE", "16000"))
TARGET_RATE = 16000
CHUNK = int(1280 * (MIC_RATE / TARGET_RATE))
WAKE_THRESHOLD = float(os.getenv("JARVIS_WAKE_THRESHOLD", "0.4"))

def is_jarvis_running():
    """Returns True if any Jarvis assistant process is already active."""
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.info['pid'] == os.getpid():
                continue
            cmdline = " ".join(proc.info.get('cmdline') or []).lower()
            if any(s in cmdline for s in ["jarvis_voice_assistant.py", "jarvis_unified.py", "jarvis_ollama.py", "jarvis_wake_controller.py"]):
                return True
        except Exception:
            continue
    return False

def listen_for_system_wake():
    print("\n" + "=" * 60)
    print("⚡ HYBRID OFFLINE WAKE LAUNCHER ONLINE")
    print("Watching for wake phrase ('Hey Jarvis')...")
    print("=" * 60 + "\n", flush=True)

    openwakeword.utils.download_models()
    oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=MIC_RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
    except Exception as e:
        print(f"⚠️ Microphone open error at {MIC_RATE}Hz: {e}")
        audio.terminate()
        return

    last_trigger = 0

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_frame = np.frombuffer(data, dtype=np.int16)

            if MIC_RATE != TARGET_RATE:
                samples = int(len(audio_frame) * TARGET_RATE / MIC_RATE)
                audio_frame = signal.resample(audio_frame, samples).astype(np.int16)

            prediction = oww_model.predict(audio_frame)
            score = prediction.get("hey_jarvis", 0.0)

            # ONLY trigger when wake word model score meets threshold
            if score >= WAKE_THRESHOLD and (time.time() - last_trigger > 5):
                last_trigger = time.time()
                print(f"\n⚡ [OPENWAKEWORD HIT] Score: {score:.3f}", flush=True)

                if is_jarvis_running():
                    print("⚡ J.A.R.V.I.S. is already running in an active window. Skipping duplicate launch.", flush=True)
                else:
                    bat_path = os.path.join(os.path.dirname(__file__), "Run_Jarvis.bat")
                    print(f"🚀 Launching {bat_path} in CMD...\n", flush=True)
                    subprocess.Popen(f'start "J.A.R.V.I.S." "{bat_path}"', shell=True)

                oww_model.reset()
                time.sleep(3)

    except KeyboardInterrupt:
        print("\nExiting Wake Launcher.")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

if __name__ == "__main__":
    listen_for_system_wake()


