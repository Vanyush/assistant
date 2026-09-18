from __future__ import annotations

import logging
from typing import Any

from core.applications import ApplicationResolver
from tools.registry import TOOLS_REGISTRY


logger = logging.getLogger(__name__)


class CommandExecutor:
    """Выполняет локальные команды без LLM."""

    def __init__(self) -> None:
        self.applications = ApplicationResolver()

    def execute(
        self,
        command: str,
        arguments: dict[str, Any],
    ) -> str:
        logger.info("Выполнение команды: %s.", command)
        logger.debug(
            "Аргументы команды %s: %s",
            command,
            arguments,
        )

        if command == "open_application":
            return self.applications.launch(
                arguments.get("app_name", "")
            )

        if command == "close_application":
            return self.applications.close(
                arguments.get("app_name", "")
            )

        function = TOOLS_REGISTRY.get(command)

        if function is None:
            return (
                "Неизвестная системная команда: "
                f"{command}"
            )

        try:
            return str(function(**arguments))
        except Exception as exc:
            logger.exception(
                "Ошибка выполнения команды: %s",
                command,
            )
            return f"Ошибка выполнения команды: {exc}"
