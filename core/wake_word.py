from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


class WakeWordDetector(ABC):
    """Общий интерфейс wake-word detector."""

    @abstractmethod
    def predict(self, audio_data: np.ndarray) -> bool:
        """Возвращает True только при новом срабатывании."""
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError


class MicroWakeWordDetector(WakeWordDetector):
    """
    Streaming wake-word detector на базе microWakeWord.

    На вход принимает PCM int16 mono, 16 kHz.
    Внутри:
        PCM -> MicroWakeWordFeatures -> TFLite model

    FIX: раньше этот класс использовал detector.process_streaming(feature),
    встроенное bool-решение, которое ничего не сообщало о реальной
    вероятности срабатывания. Если probability_cutoff модели оказывался
    чуть выше реального пика вероятности для "Джарвис", детектор молча
    никогда не срабатывал — и это было невозможно увидеть в логах.

    Теперь используется process_streaming_prob() + явное сравнение с
    настраиваемым cutoff, а при debug=True вероятность печатается в
    реальном времени — то же самое, что делал test_mww.py при ручной
    калибровке, но прямо в рабочем пайплайне main.py.
    """

    SAMPLE_RATE = 16000

    def __init__(
        self,
        config_path: str | Path,
        cooldown_seconds: float = 1.5,
        probability_cutoff: float | None = None,
        debug: bool = False,
    ) -> None:
        from pymicro_wakeword import (
            MicroWakeWord,
            MicroWakeWordFeatures,
        )

        self.config_path = Path(config_path)
        self.cooldown_seconds = cooldown_seconds
        self.cooldown_until = 0.0
        self.debug = debug

        self.features = MicroWakeWordFeatures()
        self.detector = MicroWakeWord.from_config(
            self.config_path
        )

        if probability_cutoff is not None:
            self.detector.probability_cutoff = probability_cutoff

    def predict(self, audio_data: np.ndarray) -> bool:
        now = time.monotonic()

        audio_data = np.asarray(audio_data, dtype=np.int16)

        if audio_data.ndim > 1:
            audio_data = audio_data[:, 0]

        audio_f32 = audio_data.astype(np.float32)
        audio_f32 -= np.mean(audio_f32)

        audio_data = np.clip(
            audio_f32,
            -32768,
            32767,
        ).astype(np.int16)

        for feature in self.features.process_streaming(
            audio_data.tobytes()
        ):
            prob = self.detector.process_streaming_prob(feature)

            if self.debug:
                print(
                    f"\r[WAKEWORD] prob={prob:.3f} "
                    f"cutoff={self.detector.probability_cutoff:.3f}   ",
                    end="",
                    flush=True,
                )

            if prob < self.detector.probability_cutoff:
                continue

            if now < self.cooldown_until:
                continue

            self.cooldown_until = now + self.cooldown_seconds

            if self.debug:
                print()

            return True

        return False

    def reset(self) -> None:
        self.features.reset()
        self.detector.reset()

        self.cooldown_until = (
            time.monotonic()
            + self.cooldown_seconds
        )


class VoskWakeWordDetector(WakeWordDetector):
    """
    Старый Vosk backend.

    Оставляем его как fallback, пока microWakeWord
    полностью не проверен.
    """

    SAMPLE_RATE = 16000

    def __init__(
        self,
        model_path: str | Path,
        wake_words: list[str] | None = None,
        cooldown_seconds: float = 1.5,
    ) -> None:
        from vosk import KaldiRecognizer, Model

        self.model = Model(str(model_path))

        self.wake_words = (
            wake_words
            or ["джарвис"]
        )

        self.cooldown_seconds = cooldown_seconds
        self.cooldown_until = 0.0

        self.KaldiRecognizer = KaldiRecognizer

        self._create_recognizer()

    def _create_recognizer(self) -> None:
        grammar = json.dumps(
            self.wake_words,
            ensure_ascii=False,
        )

        self.recognizer = self.KaldiRecognizer(
            self.model,
            self.SAMPLE_RATE,
            grammar,
        )

    def predict(
        self,
        audio_data: np.ndarray,
    ) -> bool:
        now = time.monotonic()

        if now < self.cooldown_until:
            return False

        audio_data = np.asarray(
            audio_data,
            dtype=np.int16,
        )

        accepted = self.recognizer.AcceptWaveform(
            audio_data.tobytes()
        )

        text = ""

        if accepted:
            result = json.loads(
                self.recognizer.Result()
            )

            text = result.get(
                "text",
                "",
            ).lower().strip()

        else:
            result = json.loads(
                self.recognizer.PartialResult()
            )

            text = result.get(
                "partial",
                "",
            ).lower().strip()

        if not self._contains_wake_word(text):
            return False

        self.cooldown_until = (
            now + self.cooldown_seconds
        )

        self.recognizer.Reset()

        return True

    def _contains_wake_word(
        self,
        text: str,
    ) -> bool:
        words = text.split()

        return any(
            word in self.wake_words
            for word in words
        )

    def reset(self) -> None:
        self.cooldown_until = (
            time.monotonic()
            + self.cooldown_seconds
        )

        self.recognizer.Reset()
