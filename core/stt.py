from faster_whisper import WhisperModel

class SpeechToText:
    """Модуль распознавания речи (Speech-to-Text) на базе Faster-Whisper."""

    def __init__(self, model_size: str = "small"):
        print(f"[STT] Загрузка модели Whisper ({model_size}) из локальной папки...")
        self.model = WhisperModel(
            model_size, 
            device="cpu", 
            compute_type="int8", 
            download_root="assets/models/whisper"
        )

    def transcribe(self, audio_file_path: str) -> str:
        """Принимает путь к WAV-файлу и возвращает распознанный текст."""
        segments, _ = self.model.transcribe(
            audio_file_path, 
            beam_size=5, 
            language="ru",
            vad_filter=True
        )
        text = " ".join([segment.text for segment in segments])
        return text.strip()