from __future__ import annotations

import logging
import os
import tempfile
import wave

from piper.voice import PiperVoice


logger = logging.getLogger(__name__)


class TextToSpeech:
    """Синтез русской речи через Piper."""

    def __init__(self, model_path: str) -> None:
        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"Piper-модель не найдена: {model_path}"
            )

        config_path = f"{model_path}.json"

        if not os.path.isfile(config_path):
            raise FileNotFoundError(
                "Конфигурация Piper не найдена: "
                f"{config_path}"
            )

        logger.info("Загрузка Piper-модели.")

        self.model = PiperVoice.load(
            model_path,
            config_path=config_path,
        )

        logger.info("Piper готов.")

    def synthesize(self, text: str) -> str:
        if not text.strip():
            return ""

        fd, output_file = tempfile.mkstemp(
            suffix=".wav",
            prefix="jarvis_tts_",
        )
        os.close(fd)

        try:
            with wave.open(output_file, "wb") as wav_file:
                self.model.synthesize_wav(text, wav_file)

            logger.debug(
                "Синтезирован файл: %s",
                output_file,
            )

            return output_file
        except Exception:
            logger.exception("Ошибка синтеза речи.")

            if os.path.exists(output_file):
                os.remove(output_file)

            return ""
