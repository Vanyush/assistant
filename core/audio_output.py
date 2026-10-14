from __future__ import annotations

import logging
import os
import subprocess


logger = logging.getLogger(__name__)


class AudioOutput:
    """Воспроизведение речи через PulseAudio или PipeWire."""

    def play(self, audio_file: str) -> None:
        if not os.path.exists(audio_file):
            logger.error(
                "Аудиофайл для воспроизведения не найден: %s",
                audio_file,
            )
            return

        if os.path.getsize(audio_file) < 100:
            logger.error(
                "Сгенерированный аудиофайл слишком мал."
            )
            return

        try:
            subprocess.run(
                ["paplay", audio_file],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.error(
                "Команда paplay не найдена. "
                "Установите pulseaudio-utils."
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Ошибка воспроизведения: код %d.",
                exc.returncode,
            )

    def stop(self) -> None:
        subprocess.run(
            ["pkill", "-x", "paplay"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
