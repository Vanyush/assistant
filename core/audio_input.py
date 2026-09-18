from __future__ import annotations

import logging
import os
import tempfile
import time
import wave
from collections import deque
from typing import Any

import numpy as np
import pyaudio

from core.wake_word import WakeWordDetector


logger = logging.getLogger(__name__)


class AudioInput:
    """Захват аудио, калибровка микрофона и запись голосовой команды."""

    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1280

    def __init__(
        self,
        wake_word_detector: WakeWordDetector,
        input_device_index: int | None = None,
        noise_multiplier: float = 3.0,
        min_speech_threshold: float = 180.0,
        max_speech_threshold: float = 500.0,
        calibration_seconds: float = 0.5,
        silence_duration: float = 1.2,
        command_timeout: float = 5.0,
        pre_roll_chunks: int = 3,
        debug: bool = False,
    ) -> None:
        self.audio = pyaudio.PyAudio()
        self.wake_word_detector = wake_word_detector
        self.input_device_index = input_device_index
        self.noise_multiplier = noise_multiplier
        self.min_speech_threshold = min_speech_threshold
        self.max_speech_threshold = max_speech_threshold
        self.calibration_seconds = calibration_seconds
        self.silence_duration = silence_duration
        self.command_timeout = command_timeout
        self.pre_roll_chunks = pre_roll_chunks
        self.debug = debug

        self.noise_floor: float | None = None
        self.speech_threshold: float | None = None
        self.last_rms_log_at = 0.0

        if self.debug:
            self._log_input_devices()

    def _log_input_devices(self) -> None:
        """Выводит устройства только в debug-логе."""
        for index in range(self.audio.get_device_count()):
            device = self.audio.get_device_info_by_index(index)
            channels = device.get("maxInputChannels", 0)

            if isinstance(channels, (int, float)) and channels > 0:
                logger.debug(
                    "Устройство ввода: index=%d name=%s",
                    index,
                    device.get("name", "unknown"),
                )

    def _open_stream(self) -> Any:
        return self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            input_device_index=self.input_device_index,
            frames_per_buffer=self.CHUNK,
        )

    def listen_for_wake_word(self) -> bool:
        """Ожидает wake-word."""
        self.wake_word_detector.reset()
        stream = self._open_stream()

        try:
            while True:
                data = stream.read(
                    self.CHUNK,
                    exception_on_overflow=False,
                )
                audio = np.frombuffer(data, dtype=np.int16)

                if self.wake_word_detector.predict(audio):
                    logger.info("Wake-word обнаружен.")
                    return True
        finally:
            stream.stop_stream()
            stream.close()

    def calibrate(self) -> None:
        """Измеряет фоновый шум и вычисляет порог речи."""
        stream = self._open_stream()

        try:
            logger.info("Калибровка микрофона…")

            noise_floor, threshold = self._calibrate_noise(
                stream
            )

            self.noise_floor = noise_floor
            self.speech_threshold = threshold

            logger.info("Микрофон откалиброван.")

            logger.debug(
                "Калибровка: noise_floor=%.1f, threshold=%.1f",
                noise_floor,
                threshold,
            )
        finally:
            stream.stop_stream()
            stream.close()

    def record_command(self) -> str:
        """Записывает команду до завершения речи."""
        if self.speech_threshold is None:
            raise RuntimeError(
                "Микрофон не откалиброван."
            )

        stream = self._open_stream()

        try:
            return self._record_from_stream(
                stream,
                self.speech_threshold,
            )
        finally:
            stream.stop_stream()
            stream.close()

    def _calibrate_noise(
        self,
        stream: Any,
    ) -> tuple[float, float]:
        rms_values: list[float] = []

        chunk_count = max(
            1,
            int(
                self.RATE
                / self.CHUNK
                * self.calibration_seconds
            ),
        )

        for _ in range(chunk_count):
            data = stream.read(
                self.CHUNK,
                exception_on_overflow=False,
            )
            audio = np.frombuffer(
                data,
                dtype=np.int16,
            ).astype(np.float32)

            rms_values.append(self._centered_rms(audio))

        noise_floor = float(np.median(rms_values))

        threshold = min(
            max(
                noise_floor * self.noise_multiplier,
                self.min_speech_threshold,
            ),
            self.max_speech_threshold,
        )

        return noise_floor, threshold

    def _record_from_stream(
        self,
        stream: Any,
        threshold: float,
    ) -> str:
        frames: list[bytes] = []
        pre_roll: deque[bytes] = deque(
            maxlen=self.pre_roll_chunks
        )

        speech_started = False
        silent_chunks = 0
        timeout_chunks = 0

        max_silent_chunks = max(
            1,
            int(
                self.RATE
                / self.CHUNK
                * self.silence_duration
            ),
        )
        max_timeout_chunks = max(
            1,
            int(
                self.RATE
                / self.CHUNK
                * self.command_timeout
            ),
        )

        logger.info("Слушаю…")

        while True:
            data = stream.read(
                self.CHUNK,
                exception_on_overflow=False,
            )
            audio = np.frombuffer(
                data,
                dtype=np.int16,
            ).astype(np.float32)

            rms = self._centered_rms(audio)
            pre_roll.append(data)

            now = time.monotonic()

            if (
                self.debug
                and now - self.last_rms_log_at >= 1.0
            ):
                logger.debug(
                    "Запись команды: rms=%.1f threshold=%.1f "
                    "speech_started=%s",
                    rms,
                    threshold,
                    speech_started,
                )
                self.last_rms_log_at = now

            if rms >= threshold:
                if not speech_started:
                    speech_started = True
                    frames.extend(pre_roll)
                else:
                    frames.append(data)

                silent_chunks = 0
                timeout_chunks = 0
                continue

            if not speech_started:
                timeout_chunks += 1

                if timeout_chunks >= max_timeout_chunks:
                    logger.info("Команда не обнаружена.")
                    return ""

                continue

            frames.append(data)
            silent_chunks += 1

            if silent_chunks >= max_silent_chunks:
                logger.info("Фраза записана.")
                break

        return self._save_wav(frames)

    @staticmethod
    def _centered_rms(audio: np.ndarray) -> float:
        """RMS аудиосигнала после удаления DC-смещения."""
        centered = audio - np.mean(audio)

        return float(
            np.sqrt(np.mean(centered**2))
        )

    def _save_wav(self, frames: list[bytes]) -> str:
        fd, path = tempfile.mkstemp(
            suffix=".wav",
            prefix="jarvis_",
        )
        os.close(fd)

        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(self.CHANNELS)
            wav_file.setsampwidth(
                self.audio.get_sample_size(self.FORMAT)
            )
            wav_file.setframerate(self.RATE)
            wav_file.writeframes(b"".join(frames))

        return path

    def close(self) -> None:
        self.audio.terminate()

    def __del__(self) -> None:
        try:
            self.audio.terminate()
        except Exception:
            pass
