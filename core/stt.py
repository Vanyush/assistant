from __future__ import annotations

import logging

from faster_whisper import WhisperModel


logger = logging.getLogger(__name__)


class SpeechToText:
    """Распознавание русской речи через Faster-Whisper."""

    def __init__(self, model_size: str = "small") -> None:
        logger.info(
            "Загрузка Whisper-модели: %s.",
            model_size,
        )

        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root="assets/models/whisper",
        )

        logger.info("Whisper готов.")

    def transcribe(self, audio_file_path: str) -> str:
        logger.debug(
            "Распознавание файла: %s",
            audio_file_path,
        )

        segments, _ = self.model.transcribe(
            audio_file_path,
            beam_size=5,
            language="ru",
            vad_filter=True,
        )

        return " ".join(
            segment.text
            for segment in segments
        ).strip()
