from __future__ import annotations

import os
import tempfile
import wave
from collections import deque

import numpy as np
import pyaudio

from core.wake_word import WakeWordDetector


class AudioInput:
    """
    Работа с микрофоном.

    Схема:

        Vosk wake word
             ↓
        beep
             ↓
        калибровка шума
             ↓
        запись команды
             ↓
        WAV
    """

    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1280

    def __init__(
        self,
        wake_word_detector: WakeWordDetector,
        noise_multiplier: float = 3.0,
        min_speech_threshold: float = 180.0,
        max_speech_threshold: float = 500.0,
        calibration_seconds: float = 0.5,
        silence_duration: float = 1.2,
        command_timeout: float = 5.0,
        pre_roll_chunks: int = 3,
    ) -> None:

        self.audio = pyaudio.PyAudio()

        self.wake_word_detector = (
            wake_word_detector
        )

        self.noise_multiplier = (
            noise_multiplier
        )

        self.min_speech_threshold = (
            min_speech_threshold
        )

        self.max_speech_threshold = (
            max_speech_threshold
        )

        self.calibration_seconds = (
            calibration_seconds
        )

        self.silence_duration = (
            silence_duration
        )

        self.command_timeout = (
            command_timeout
        )

        self.pre_roll_chunks = (
            pre_roll_chunks
        )

        self.noise_floor: float | None = None
        self.speech_threshold: float | None = None

    # ==================================================================
    # WAKE WORD
    # ==================================================================

    def listen_for_wake_word(self) -> bool:
        """
        Ожидание wake word.
        """

        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

        print(
            '\n[AUDIO] '
            'Ожидание "Джарвис"...'
        )

        try:
            while True:

                data = stream.read(
                    self.CHUNK,
                    exception_on_overflow=False,
                )

                audio = np.frombuffer(
                    data,
                    dtype=np.int16,
                )

                detected = (
                    self.wake_word_detector.predict(
                        audio
                    )
                )

                if detected:

                    print(
                        '\n[AUDIO] '
                        'Wake word обнаружен.'
                    )

                    return True

        finally:
            stream.stop_stream()
            stream.close()

    # ==================================================================
    # CALIBRATION
    # ==================================================================

    def calibrate(self) -> None:
        """
        Однократная калибровка фонового шума.

        Вызывается один раз перед запуском основного цикла.
        Результат сохраняется в self.noise_floor
        и self.speech_threshold.
        """

        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

        try:
            print(
                '\n[AUDIO] '
                'Калибровка микрофона...'
            )

            print(
                '[AUDIO] '
                f'Не говорите {self.calibration_seconds:.1f} с.'
            )

            threshold = self._calibrate_noise(
                stream
            )

            self.speech_threshold = threshold

            print(
                '[AUDIO] '
                f'Порог речи: '
                f'{threshold:.1f}'
            )

            print(
                '[AUDIO] '
                'Калибровка завершена.'
            )

        finally:
            stream.stop_stream()
            stream.close()

    # ==================================================================
    # COMMAND RECORDING
    # ==================================================================

    def record_command(self) -> str:
        """
        Записывает голосовую команду.

        Сначала вычисляется уровень фонового шума.
        При расчёте всегда удаляется DC offset.
        """

        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

        try:

            if self.speech_threshold is None:
                raise RuntimeError(
                    'Микрофон не откалиброван. '
                    'Сначала вызовите audio.calibrate().'
                )

            return self._record_from_stream(
                stream,
                self.speech_threshold,
            )

        finally:

            stream.stop_stream()
            stream.close()

    # ==================================================================
    # CALIBRATION
    # ==================================================================

    def _calibrate_noise(
        self,
        stream,
    ) -> float:
        """
        Оценивает уровень тишины.

        Ключевые свойства:

        1. Удаляется DC offset.
        2. Используется медиана/percentile,
           а не максимум.
        3. Порог ограничен сверху.
        """

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

            rms = self._centered_rms(
                audio
            )

            rms_values.append(rms)

        # Основной уровень фонового шума.
        noise_floor = float(
            np.median(
                rms_values
            )
        )

        threshold = (
            noise_floor
            * self.noise_multiplier
        )

        # Нижняя граница.
        threshold = max(
            threshold,
            self.min_speech_threshold,
        )

        # Верхняя граница.
        threshold = min(
            threshold,
            self.max_speech_threshold,
        )

        print(
            '[AUDIO] '
            f'Noise floor: '
            f'{noise_floor:.1f}'
        )

        return threshold

    # ==================================================================
    # RECORD
    # ==================================================================

    def _record_from_stream(
        self,
        stream,
        threshold: float,
    ) -> str:

        frames: list[bytes] = []

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

        pre_roll: deque[bytes] = deque(
            maxlen=self.pre_roll_chunks
        )

        print(
            '[AUDIO] '
            'Говорите...'
        )

        while True:

            data = stream.read(
                self.CHUNK,
                exception_on_overflow=False,
            )

            audio = np.frombuffer(
                data,
                dtype=np.int16,
            ).astype(np.float32)

            rms = self._centered_rms(
                audio
            )

            print(
                '\r[AUDIO] '
                f'RMS={rms:6.1f} '
                f'{"SPEECH" if speech_started else "WAIT"}   ',
                end='',
                flush=True,
            )

            pre_roll.append(data)

            # ----------------------------------------------------------
            # Речь обнаружена
            # ----------------------------------------------------------

            if rms >= threshold:

                if not speech_started:

                    speech_started = True

                    # Добавляем несколько предыдущих chunks,
                    # чтобы не потерять начало слова.
                    frames.extend(
                        pre_roll
                    )

                else:

                    frames.append(
                        data
                    )

                silent_chunks = 0
                timeout_chunks = 0

                continue

            # ----------------------------------------------------------
            # Тишина
            # ----------------------------------------------------------

            if not speech_started:

                timeout_chunks += 1

                if (
                    timeout_chunks
                    >= max_timeout_chunks
                ):
                    print(
                        '\n[AUDIO] '
                        'Команда не обнаружена.'
                    )

                    return ''

            else:

                frames.append(
                    data
                )

                silent_chunks += 1

                if (
                    silent_chunks
                    >= max_silent_chunks
                ):

                    print(
                        '\n[AUDIO] '
                        'Конец фразы.'
                    )

                    break

        if not frames:
            return ''

        return self._save_wav(
            frames
        )

    # ==================================================================
    # SIGNAL PROCESSING
    # ==================================================================

    @staticmethod
    def _centered_rms(
        audio: np.ndarray,
    ) -> float:
        """
        RMS после удаления DC offset.

        Для твоего микрофона это критично:
        raw signal находится примерно около 8192.
        """

        centered = (
            audio
            - np.mean(audio)
        )

        return float(
            np.sqrt(
                np.mean(
                    centered ** 2
                )
            )
        )

    # ==================================================================
    # WAV
    # ==================================================================

    def _save_wav(
        self,
        frames: list[bytes],
    ) -> str:

        fd, path = tempfile.mkstemp(
            suffix='.wav',
            prefix='jarvis_',
        )

        os.close(fd)

        with wave.open(
            path,
            'wb',
        ) as wav:

            wav.setnchannels(
                self.CHANNELS
            )

            wav.setsampwidth(
                self.audio.get_sample_size(
                    self.FORMAT
                )
            )

            wav.setframerate(
                self.RATE
            )

            wav.writeframes(
                b''.join(frames)
            )

        return path

    # ==================================================================
    # CLEANUP
    # ==================================================================

    def close(self) -> None:
        self.audio.terminate()

    def __del__(self) -> None:
        try:
            self.audio.terminate()
        except Exception:
            pass
