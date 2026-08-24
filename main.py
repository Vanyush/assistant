import asyncio
import os
import re
import yaml

from core.llm import Brain
from core.stt import SpeechToText
from core.audio_input import AudioInput
from core.audio_feedback import AudioFeedback
from core.tts import TextToSpeech
from core.audio_output import AudioOutput


async def main() -> None:
    """Главный цикл работы голосового ассистента."""
    print("[SYSTEM] Загрузка конфигурации...")
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print(f"[SYSTEM] Инициализация мозга ({config['llm']['model']})...")
    brain = Brain(
        model_name=config['llm']['model'],
        system_prompt_path="config/system_prompt.txt"
    )
    
    # Инициализация звуковых модулей
    stt = SpeechToText(model_size=config['stt']['whisper_model'])
    mic = AudioInput()
    feedback = AudioFeedback()
    
    # Сборка пути к модели Piper
    piper_model_path = os.path.join(
        "assets", "models", "piper", config["tts"]["piper_model"]
    )
    tts = TextToSpeech(model_path=piper_model_path)
    speaker = AudioOutput()

    print("\n" + "-" * 50)
    print("[SYSTEM] Система готова. Ожидание команды 'Джарвис'")
    print("-" * 50)

    while True:
        try:
            # 1. Ждем фразу "Джарвис"
            mic.listen_for_wake_word()
            feedback.play_activation()
            
            # 2. Записываем команду до тишины
            audio_file = mic.record_command()
            if not audio_file:
                print("[SYSTEM] Команда не была записана.")
                continue
            
            # 3. Распознаем речь
            print("[STT] Распознавание...")
            user_text = stt.transcribe(audio_file)
            print(f"\nВы сказали: {user_text}")
            
            # Удаляем временный файл с голосом
            if os.path.exists(audio_file):
                os.remove(audio_file)

            if not user_text.strip():
                print("[SYSTEM] Ничего не услышал. Возврат в режим ожидания.")
                continue

            # 4. Передаем текст в LLM
            print("[LLM] Думаю...")
            response = brain.process_input(user_text)
            print(f"\nДжарвис: {response}")
            
            # 5. Глубокая очистка и подготовка текста для Piper
            clean_response = re.sub(r'[*_#`~]', '', response)
            
            # Заменяем символы, которые ломают TTS (например, "69.0°C" -> "69.0 градусов")
            clean_response = clean_response.replace('°C', ' градусов')
            clean_response = clean_response.replace('CPU', 'процессора')
            clean_response = clean_response.replace('%', ' процента')
            
            # Убираем всё, кроме русских букв, цифр, знаков препинания и пробелов
            # Это гарантирует, что Piper не подавится мусорными символами
            clean_response = re.sub(r'[^А-Яа-яЁё0-9.,!?:\-\s]', '', clean_response)

            # 6. Синтез речи
            synthesized_file = tts.synthesize(clean_response)

            # 7. Воспроизведение
            if synthesized_file:
                speaker.play(synthesized_file)
                if os.path.exists(synthesized_file):
                    os.remove(synthesized_file)

        except KeyboardInterrupt:
            print("\n[SYSTEM] Принудительное завершение работы (Ctrl+C)...")
            break
        except Exception as e:
            print(f"[ОШИБКА] Произошел сбой в главном цикле: {e}")

    print("[SYSTEM] Отключение систем...")

if __name__ == "__main__":
    asyncio.run(main())