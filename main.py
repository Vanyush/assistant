from __future__ import annotations

import asyncio
import logging
import os
import re

import yaml

from core.audio_feedback import AudioFeedback
from core.audio_input import AudioInput
from core.audio_output import AudioOutput
from core.executor import CommandExecutor
from core.llm import Brain
from core.logging_config import configure_logging
from core.router import CommandRouter
from core.stt import SpeechToText
from core.tts import TextToSpeech
from core.wake_word import (
    MicroWakeWordDetector,
    VoskWakeWordDetector,
)


logger = logging.getLogger(__name__)


def sanitize_for_tts(text: str) -> str:
    """Очищает ответ для корректного синтеза Piper."""
    text = re.sub(r"[*_#`~]", "", text)
    text = text.replace("°C", " градусов")
    text = text.replace("CPU", "процессора")
    text = text.replace("%", " процента")

    return re.sub(
        r"[^А-Яа-яЁё0-9.,!?:\-\s]",
        "",
        text,
    )


def load_config() -> dict:
    with open(
        "config/config.yaml",
        "r",
        encoding="utf-8",
    ) as config_file:
        return yaml.safe_load(config_file)


async def main() -> None:
    config = load_config()
    configure_logging(config.get("logging"))

    assistant_name = config["assistant"]["name"]
    wake_word = config["assistant"]["wake_word"]
    wake_config = config["wake_word"]
    audio_config = config.get("audio", {})

    logger.info("Запуск ассистента %s.", assistant_name)

    brain = Brain(
        model_name=config["llm"]["model"],
        system_prompt_path="config/system_prompt.txt",
        base_url=config["llm"]["host"],
        temperature=config["llm"].get("temperature", 0.2),
        max_tokens=config["llm"].get("max_tokens", 256),
    )
    router = CommandRouter()
    executor = CommandExecutor()

    stt = SpeechToText(
        model_size=config["stt"]["whisper_model"]
    )

    wake_backend = wake_config.get(
        "backend",
        "microwakeword",
    ).lower()
    cooldown_seconds = wake_config.get(
        "cooldown_seconds",
        1.5,
    )

    if wake_backend == "microwakeword":
        wake_detector = MicroWakeWordDetector(
            config_path=wake_config["model"],
            cooldown_seconds=cooldown_seconds,
            probability_cutoff=wake_config.get(
                "probability_cutoff"
            ),
            debug=wake_config.get("debug", False),
        )
    elif wake_backend == "vosk":
        wake_detector = VoskWakeWordDetector(
            model_path=wake_config["model"],
            wake_words=[wake_word.lower()],
            cooldown_seconds=cooldown_seconds,
        )
    else:
        raise ValueError(
            "Неизвестный wake-word backend: "
            f"{wake_backend}"
        )

    microphone = AudioInput(
        wake_word_detector=wake_detector,
        input_device_index=audio_config.get(
            "input_device_index"
        ),
        debug=audio_config.get("debug", False),
    )
    microphone.calibrate()

    feedback = AudioFeedback()

    piper_model_path = os.path.join(
        "assets",
        "models",
        "piper",
        config["tts"]["piper_model"],
    )
    tts = TextToSpeech(model_path=piper_model_path)
    speaker = AudioOutput()

    logger.info(
        "Ассистент готов. Скажите «%s».",
        wake_word,
    )

    try:
        while True:
            try:
                logger.info(
                    "Ожидание wake-word: «%s».",
                    wake_word,
                )

                microphone.listen_for_wake_word()
                feedback.play_activation()

                audio_file = microphone.record_command()

                if not audio_file:
                    continue

                try:
                    user_text = stt.transcribe(audio_file)
                finally:
                    try:
                        os.unlink(audio_file)
                    except FileNotFoundError:
                        pass

                if not user_text:
                    logger.info(
                        "Речь не распознана. "
                        "Возврат в режим ожидания."
                    )
                    continue

                logger.info("Пользователь: %s", user_text)

                route = router.route(user_text)

                if route is not None:
                    response = executor.execute(
                        route.command,
                        route.arguments,
                    )
                else:
                    response = brain.process_input(user_text)

                clean_response = sanitize_for_tts(response)

                if not clean_response:
                    logger.warning(
                        "После очистки для TTS ответ пуст."
                    )
                    continue

                synthesized_file = tts.synthesize(
                    clean_response
                )

                if synthesized_file:
                    try:
                        speaker.play(synthesized_file)
                    finally:
                        try:
                            os.remove(synthesized_file)
                        except FileNotFoundError:
                            pass

            except KeyboardInterrupt:
                raise
            except Exception:
                logger.exception(
                    "Ошибка главного цикла."
                )

    except KeyboardInterrupt:
        logger.info("Завершение работы по Ctrl+C.")
    finally:
        microphone.close()
        logger.info("Ассистент остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
