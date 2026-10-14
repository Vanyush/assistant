from __future__ import annotations

import logging
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)


class AudioFeedback:
    """Короткие системные звуки ассистента."""

    def __init__(self) -> None:
        self.activation_sound = (
            Path(__file__).parent.parent
            / "assets"
            / "sounds"
            / "activation.wav"
        )

    def play_activation(self) -> None:
        if not self.activation_sound.is_file():
            logger.warning(
                "Звук активации не найден: %s",
                self.activation_sound,
            )
            return

        try:
            subprocess.Popen(
                ["paplay", str(self.activation_sound)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning(
                "Команда paplay не найдена."
            )
        except OSError:
            logger.exception(
                "Не удалось воспроизвести звук активации."
            )
