from pathlib import Path

from pymicro_wakeword import MicroWakeWord


MODEL = Path(
    "assets/models/wake_word/ru_jarvis_mww.tflite"
)


def main():
    print("[TEST] Loading model...")

    # Используем тот же способ загрузки, что и основной проект.
    detector = MicroWakeWord(
        model_path=MODEL.read_bytes()
    )

    print("\n[DEBUG] detector:")
    print(detector.__dict__)

    print("\n[DEBUG] input:")
    print("dtype:", detector.input_dtype)
    print("scale:", detector.input_scale)
    print("zero_point:", detector.input_zero_point)

    print("\n[DEBUG] output:")
    print("dtype:", detector.output_dtype)
    print("scale:", detector.output_scale)
    print("zero_point:", detector.output_zero_point)


if __name__ == "__main__":
    main()
