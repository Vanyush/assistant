import os
import subprocess
from pathlib import Path


class AudioOutput:
    """Модуль воспроизведения речи через системный звуковой сервер (PulseAudio/PipeWire)."""

    def __init__(self):
        print(" [AUDIO] Инициализация аудиовыхода (paplay)...")

    def play(self, audio_file: str) -> None:
        """Воспроизводит WAV-файл и ждет окончания воспроизведения."""
        if not os.path.exists(audio_file):
            print(f"[ОШИБКА] Аудиофайл для воспроизведения не найден: {audio_file}")
            return

        if os.path.getsize(audio_file) < 100:
            print("[ОШИБКА] Сгенерированный аудиофайл слишком мал (возможно, пуст).")
            return

        print(" [AUDIO] Воспроизведение ответа...")
        try:
            # Используем run, чтобы ассистент договорил фразу до конца, 
            # прежде чем снова начать слушать микрофон
            subprocess.run(
                ["paplay", audio_file],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except FileNotFoundError:
            print("[ОШИБКА] Команда 'paplay' не найдена. Установите пакет pulseaudio-utils.")
        except subprocess.CalledProcessError as e:
            print(f"[ОШИБКА] Сбой при воспроизведении аудио: код {e.returncode}")

    def stop(self) -> None:
        """Останавливает воспроизведение всех процессов paplay."""
        subprocess.run(
            ["pkill", "-x", "paplay"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )