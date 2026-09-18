from __future__ import annotations

import contextlib
import io
import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


logger = logging.getLogger(__name__)


class WakeWordDetector(ABC):
    """Общий интерфейс детектора wake-word."""

    @abstractmethod
    def predict(self, audio_data: np.ndarray) -> bool:
        """Возвращает True при новом срабатывании."""
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        """Сбрасывает внутреннее состояние детектора."""
        raise NotImplementedError


class MicroWakeWordDetector(WakeWordDetector):
    """Streaming wake-word detector на базе microWakeWord."""

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
        self.last_debug_log_at = 0.0

        self.features = MicroWakeWordFeatures()

        if not self.config_path.is_file():
            raise FileNotFoundError(
                "Конфигурация wake-word не найдена: "
                f"{self.config_path}"
            )

        captured_stdout = io.StringIO()

        try:
            with contextlib.redirect_stdout(captured_stdout):
                self.detector = MicroWakeWord.from_config(
                    self.config_path
                )
        except Exception as exc:
            raise RuntimeError(
                "Не удалось загрузить microWakeWord-модель "
                f"из {self.config_path}: {exc}"
            ) from exc

        library_output = captured_stdout.getvalue().strip()

        if library_output:
            logger.debug(
                "Вывод pymicro_wakeword при загрузке: %s",
                library_output,
            )

        if probability_cutoff is not None:
            self.detector.probability_cutoff = probability_cutoff

        logger.info(
            "Wake-word модель загружена: %s",
            self.config_path.name,
        )
        logger.debug(
            "Wake-word параметры: cutoff=%.3f, cooldown=%.1f с",
            self.detector.probability_cutoff,
            self.cooldown_seconds,
        )

    def predict(self, audio_data: np.ndarray) -> bool:
        now = time.monotonic()

        audio_data = np.asarray(audio_data, dtype=np.int16)

        if audio_data.ndim > 1:
            audio_data = audio_data[:, 0]

        max_amplitude = int(np.abs(audio_data).max())

        for feature in self.features.process_streaming(
            audio_data.tobytes()
        ):
            probability = self.detector.process_streaming_prob(
                feature
            )

            if (
                self.debug
                and now - self.last_debug_log_at >= 1.0
            ):
                logger.debug(
                    "Wake-word: probability=%.3f cutoff=%.3f "
                    "max_amplitude=%d",
                    probability,
                    self.detector.probability_cutoff,
                    max_amplitude,
                )
                self.last_debug_log_at = now

            if probability < self.detector.probability_cutoff:
                continue

            if now < self.cooldown_until:
                continue

            self.cooldown_until = now + self.cooldown_seconds

            logger.info(
                "Wake-word обнаружен: probability=%.3f",
                probability,
            )
            return True

        return False

    def reset(self) -> None:
        self.features.reset()
        self.detector.reset()
        self.cooldown_until = (
            time.monotonic() + self.cooldown_seconds
        )


class VoskWakeWordDetector(WakeWordDetector):
    """Wake-word detector на базе Vosk."""

    SAMPLE_RATE = 16000

    def __init__(
        self,
        model_path: str | Path,
        wake_words: list[str] | None = None,
        cooldown_seconds: float = 1.5,
    ) -> None:
        from vosk import KaldiRecognizer, Model

        self.model_path = Path(model_path)

        if not self.model_path.is_dir():
            raise FileNotFoundError(
                "Vosk-модель не найдена: "
                f"{self.model_path}"
            )

        self.model = Model(str(self.model_path))
        self.wake_words = [
            word.lower().strip()
            for word in (wake_words or ["джарвис"])
        ]
        self.cooldown_seconds = cooldown_seconds
        self.cooldown_until = 0.0
        self.KaldiRecognizer = KaldiRecognizer

        self._create_recognizer()

        logger.info(
            "Vosk wake-word загружен: %s",
            ", ".join(self.wake_words),
        )

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

    def predict(self, audio_data: np.ndarray) -> bool:
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

        if accepted:
            result = json.loads(self.recognizer.Result())
            text = result.get("text", "")
        else:
            result = json.loads(
                self.recognizer.PartialResult()
            )
            text = result.get("partial", "")

        text = text.lower().strip()

        if not self._contains_wake_word(text):
            return False

        self.cooldown_until = now + self.cooldown_seconds
        self.recognizer.Reset()

        logger.info("Wake-word обнаружен: %s", text)
        return True

    def _contains_wake_word(self, text: str) -> bool:
        return any(
            wake_word in text
            for wake_word in self.wake_words
        )

    def reset(self) -> None:
        self.cooldown_until = (
            time.monotonic() + self.cooldown_seconds
        )
        self.recognizer.Reset()
