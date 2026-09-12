import pyaudio
import numpy as np

p = pyaudio.PyAudio()

print("\n--- DETECTED AUDIO INPUTS ---")
for i in range(p.get_device_count()):
    try:
        dev = p.get_device_info_by_host_api_device_index(0, i)
        if dev.get('maxInputChannels', 0) > 0:
            print(f"Device Index [{i}]: {dev.get('name')} (Default Sample Rate: {int(dev.get('defaultSampleRate', 0))} Hz)")
    except Exception as e:
        pass

print("\nListening to default device... Speak loudly now!")
try:
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1280)

    for i in range(50):
        data = stream.read(1280, exception_on_overflow=False)
        frame = np.frombuffer(data, dtype=np.int16)
        rms = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
        print(f"[{i+1}/50] Volume RMS: {int(rms):<5} | {'[LOUD]' if rms > 150 else '[SILENCE / TOO LOW]'}")

    stream.stop_stream()
    stream.close()
except Exception as err:
    print(f"\n⚠️ Recording failed: {err}")
    print("If error is 'Invalid sample rate', your hardware requires 44100 Hz or 48000 Hz downsampling.")

p.terminate()

