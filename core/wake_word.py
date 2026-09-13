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


class VoskWakeWordDetector(WakeWordDetector):
    """
    Временный русскоязычный wake-word backend на Vosk.

    Vosk работает как continuous ASR с ограниченной grammar.
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

        # --------------------------------------------------------------
        # NEW EVENT
        # --------------------------------------------------------------

        self.cooldown_until = (
            now + self.cooldown_seconds
        )

        # Полностью начинаем новый ASR segment.
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
