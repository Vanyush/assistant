import os
import tempfile
import wave
import pyaudio
import numpy as np
from openwakeword.model import Model


class AudioInput:
    """Модуль работы с микрофоном: ожидание Wake Word и запись команд."""

    def __init__(self):
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000  # openWakeWord требует 16kHz
        self.CHUNK = 1280
        
        self.audio = pyaudio.PyAudio()
        print(" [AUDIO] Загрузка Wake Word модели 'Jarvis'...")
        self.oww_model = Model(
            wakeword_models=["assets/models/wake_word/hey_jarvis_v0.1.tflite"],
            vad_threshold=0.5
        )

    def listen_for_wake_word(self) -> bool:
        """Слушает микрофон до произнесения Wake Word."""
        stream = self.audio.open(
            format=self.FORMAT, channels=self.CHANNELS,
            rate=self.RATE, input=True, frames_per_buffer=self.CHUNK
        )
        print("\n[AUDIO] Слушаю эфир (скажи 'Джарвис')...")
        
        try:
            while True:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                
                prediction = self.oww_model.predict(audio_data)
                max_score = max(prediction.values()) if prediction else 0.0

                print(f"\r[WAKE] score={max_score:.3f}", end="", flush=True)

                if max_score > 0.15:
                    print(f"\n[AUDIO] Зафиксировано слово активации (уверенность: {max_score:.2f})!")
                    stream.stop_stream()
                    stream.close()
                    self.oww_model.reset()
                    return True
        except KeyboardInterrupt:
            stream.close()
            raise

    def record_command(
        self, silence_threshold: int = 1000, silence_duration: float = 1.5, start_timeout: float = 5.0
    ) -> str:
        """Записывает аудио с микрофона до наступления тишины."""
        stream = self.audio.open(
            format=self.FORMAT, channels=self.CHANNELS,
            rate=self.RATE, input=True, frames_per_buffer=self.CHUNK
        )
        print("[AUDIO] Запись команды...")

        frames = []
        silent_chunks = 0
        speech_started = False
        start_chunks = 0

        max_silent_chunks = int((self.RATE / self.CHUNK) * silence_duration)
        max_start_chunks = int((self.RATE / self.CHUNK) * start_timeout)

        try:
            while True:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                rms = np.std(audio_data)

                print(f"\r[AUDIO] RMS={rms:.0f} {'SPEECH' if speech_started else 'WAIT'}   ", end="", flush=True)

                if rms >= silence_threshold:
                    # Человек говорит
                    speech_started = True
                    silent_chunks = 0
                    start_chunks = 0
                    frames.append(data)
                else:
                    if not speech_started:
                        # Ожидание начала речи
                        start_chunks += 1
                        if start_chunks >= max_start_chunks:
                            print("\n[AUDIO] Команда не обнаружена (таймаут).")
                            return ""
                    else:
                        # Речь была, фиксируем тишину
                        frames.append(data)
                        silent_chunks += 1
                        if silent_chunks >= max_silent_chunks:
                            print("\n[AUDIO] Конец фразы (тишина).")
                            break
        finally:
            stream.stop_stream()
            stream.close()

        # Создаём временный WAV файл
        fd, file_path = tempfile.mkstemp(suffix=".wav", prefix="jarvis_")
        os.close(fd)

        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b"".join(frames))

        return file_path