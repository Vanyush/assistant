from __future__ import annotations

from pathlib import Path

import numpy as np
import sounddevice as sd

from core.wake_word import VoskWakeWordDetector


MODEL_PATH = Path(
    "assets/models/wake_word/vosk/"
    "vosk-model-small-ru-0.22"
)


def main() -> None:

    print(
        "Загрузка Vosk..."
    )

    detector = VoskWakeWordDetector(
        MODEL_PATH,
        wake_words=["джарвис"],
        cooldown_seconds=1.5,
    )

    print(
        '\nСистема готова. '
        'Скажи "Джарвис".'
    )

    while True:

        audio = sd.rec(
            1280,
            samplerate=16000,
            channels=1,
            dtype="int16",
            blocking=True,
        )

        audio = audio[:, 0]

        if detector.predict(audio):

            print(
                "\n>>> "
                "ДЖАРВИС ОБНАРУЖЕН "
                "<<<"
            )


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print(
            "\nОстановка."
        )
