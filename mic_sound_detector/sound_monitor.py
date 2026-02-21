#!/usr/bin/env python3
import pyaudio
import struct
import math
import time

# 🔧 Adjust this threshold — lower = more sensitive
THRESHOLD = 500
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def get_rms(data):
    count = len(data) // 2
    shorts = struct.unpack('%dh' % count, data)
    sum_squares = sum(s * s for s in shorts)
    rms = math.sqrt(sum_squares / count) if count > 0 else 0
    return rms

p = pyaudio.PyAudio()

print("🎤 Mic Sound Detector started!")
print(f"   Threshold: {THRESHOLD} — lower this number to be more sensitive")
print("   Listening...")

try:
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    last_sound_time = 0

    while True:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = get_rms(data)

            if rms > THRESHOLD:
                now = time.time()
                # Only log once per second to avoid spam
                if now - last_sound_time > 1.0:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] 🔊 SOUND DETECTED! Level: {int(rms)}")
                    last_sound_time = now

        except Exception as e:
            print(f"Read error: {e}")
            time.sleep(0.1)

except Exception as e:
    print(f"❌ Could not open microphone: {e}")
    print("   Check that your mic is connected and audio: true is in config.yaml")

finally:
    if 'stream' in dir():
        stream.stop_stream()
        stream.close()
    p.terminate()