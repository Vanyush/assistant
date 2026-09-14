from pathlib import Path

import numpy as np
import sounddevice as sd

from pymicro_wakeword import MicroWakeWord
from pymicro_wakeword import MicroWakeWordFeatures


CONFIG = Path("assets/models/wake_word/ru_jarvis_mww.json")

RATE = 16000
CHUNK = 160


def main():
    print("[TEST] Loading model...")

    detector = MicroWakeWord.from_config(CONFIG)
    print("\n[DEBUG] detector:")
    print(detector.__dict__.keys())

    print("\n[DEBUG] model:")
    print("id:", detector.id)
    print("wake_word:", detector.wake_word)
    print("model_path:", detector.model_path)
    print("model:", detector.model)
    print("tflite_model:", detector.tflite_model)

    print("\n[DEBUG] input:")
    print("input_tensor:", detector.input_tensor)
    print("input_dtype:", detector.input_dtype)
    print("input_scale:", detector.input_scale)
    print("input_zero_point:", detector.input_zero_point)

    print("\n[DEBUG] output:")
    print("output_tensor:", detector.output_tensor)
    print("output_dtype:", detector.output_dtype)
    print("output_scale:", detector.output_scale)
    print("output_zero_point:", detector.output_zero_point)

    print("\n[DEBUG] parameters:")
    print("probability_cutoff:", detector.probability_cutoff)
    print("sliding_window_size:", detector.sliding_window_size)
    print("stride:", detector.stride)
    features = MicroWakeWordFeatures()

    print("[TEST] Model loaded")
    print("[TEST] Say: Джарвис")
    print()

    counter = 0

    try:
        while True:
            audio = sd.rec(
                CHUNK,
                samplerate=RATE,
                channels=1,
                dtype="int16",
                blocking=True,
            )

            audio = np.asarray(audio[:, 0], dtype=np.int16)

            audio_f32 = audio.astype(np.float32)
            audio_f32 -= np.mean(audio_f32)

            audio = np.clip(
                audio_f32,
                -32768,
                32767,
            ).astype(np.int16)

            rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
            peak = np.max(np.abs(audio))

            for feature in features.process_streaming(audio.tobytes()):
                prob = detector.process_streaming_prob(feature)

                print(
                    f"RMS={rms:7.1f}",
                    f"PEAK={peak:5d}",
                    f"FEATURE: shape={feature.shape}",
                    f"dtype={feature.dtype}",
                    f"min={feature.min():.3f}",
                    f"max={feature.max():.3f}",
                    f"mean={feature.mean():.3f}",
                    f"prob={prob:.6f}",
                )

    except KeyboardInterrupt:
        print("\n[TEST] Stopped")

    finally:
        detector.close()


if __name__ == "__main__":
    main()
