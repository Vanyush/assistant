import os
import tempfile
import wave
from piper.voice import PiperVoice


class TextToSpeech:
    """Модуль синтеза речи (Text-to-Speech) на базе Piper."""

    def __init__(self, model_path: str):
        print(" [TTS] Загрузка модели Piper...")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Piper модель не найдена: {model_path}")

        config_path = model_path + ".json"
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Конфигурация Piper не найдена: {config_path}")

        self.model = PiperVoice.load(model_path, config_path=config_path)
        print(" [TTS] Piper готов.")

    def synthesize(self, text: str) -> str:
        """Преобразует текст в WAV-файл с помощью встроенного метода Piper."""
        if not text or not text.strip():
            return ""

        fd, output_file = tempfile.mkstemp(suffix=".wav", prefix="jarvis_tts_")
        os.close(fd)

        print(" [TTS] Синтез речи...")
        try:
            # Используем родной метод библиотеки для записи в wave-контейнер
            with wave.open(output_file, "wb") as wav_file:
                self.model.synthesize_wav(text, wav_file)
            
            return output_file

        except Exception as e:
            print(f" [ОШИБКА TTS] Ошибка при синтезе речи: {e}")
            if os.path.exists(output_file):
                os.remove(output_file)
            return ""