import pyaudio
import numpy as np
import openwakeword
from openwakeword.model import Model

try:
    openwakeword.utils.download_models()
except Exception:
    pass

oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

p = pyaudio.PyAudio()
stream = p.open(rate=16000, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=1280)

print("\n" + "="*45)
print(" SPEAK NOW: Say 'Hey Jarvis' repeatedly")
print("="*45 + "\n")

while True:
    try:
        data = stream.read(1280, exception_on_overflow=False)
        frame = np.frombuffer(data, dtype=np.int16)
        
        rms = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
        score = oww_model.predict(frame).get("hey_jarvis", 0.0)

        # Print live metrics
        if rms > 80 or score > 0.1:
            print(f"Mic Energy (RMS): {int(rms):<5} | Hey Jarvis Confidence: {score:.3f}")
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"Error: {e}")

stream.stop_stream()
stream.close()
p.terminate()
