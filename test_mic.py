import numpy as np
import sounddevice as sd

RATE = 16000
CHUNK = 160


print("Говори в микрофон. Ctrl+C для выхода.")

try:
    while True:
        audio = sd.rec(
            CHUNK,
            samplerate=RATE,
            channels=1,
            dtype="int16",
            blocking=True,
        )

        audio = audio[:, 0].astype(np.float32)

        raw_mean = np.mean(audio)
        centered = audio - raw_mean

        rms_raw = np.sqrt(np.mean(audio ** 2))
        rms_centered = np.sqrt(np.mean(centered ** 2))
        peak = np.max(np.abs(centered))

        print(
            f"mean={raw_mean:8.1f} "
            f"rms_raw={rms_raw:8.1f} "
            f"rms_centered={rms_centered:8.1f} "
            f"peak={peak:6.0f}"
        )

except KeyboardInterrupt:
    print("\nStopped")
