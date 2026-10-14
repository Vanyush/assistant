from __future__ import annotations

import asyncio
import logging

import yaml

from core.executor import CommandExecutor
from core.llm import Brain
from core.logging_config import configure_logging
from core.router import CommandRouter


logger = logging.getLogger(__name__)


async def main() -> None:
    with open(
        "config/config.yaml",
        "r",
        encoding="utf-8",
    ) as config_file:
        config = yaml.safe_load(config_file)

    configure_logging(config.get("logging"))

    brain = Brain(
        model_name=config["llm"]["model"],
        system_prompt_path="config/system_prompt.txt",
        base_url=config["llm"]["host"],
        temperature=config["llm"].get("temperature", 0.2),
        max_tokens=config["llm"].get("max_tokens", 256),
    )
    router = CommandRouter()

    executor = CommandExecutor(
        spotify_config=config.get(
            "spotify",
            {},
        )
    )

    logger.info(
        "Текстовый режим готов. "
        "Для выхода: exit."
    )

    while True:
        try:
            user_input = input("\nВы: ").strip()

            if user_input.lower() in {
                "exit",
                "выход",
                "quit",
            }:
                break

            if not user_input:
                continue

            route = router.route(user_input)

            if route is not None:
                response = executor.execute(
                    route.command,
                    route.arguments,
                )
            else:
                response = brain.process_input(user_input)

            logger.info("Джарвис: %s", response)

        except KeyboardInterrupt:
            break
        except Exception:
            logger.exception(
                "Ошибка текстового режима."
            )

    logger.info("Текстовый режим остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
