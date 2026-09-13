from __future__ import annotations

from typing import Any

from core.applications import ApplicationResolver
from tools.registry import TOOLS_REGISTRY


class CommandExecutor:
    """
    Выполняет локальные команды без LLM.
    """

    def __init__(self) -> None:
        self.applications = ApplicationResolver()

    def execute(
        self,
        command: str,
        arguments: dict[str, Any],
    ) -> str:

        print(
            f"[SYSTEM] Выполнение: "
            f"{command}({arguments})"
        )

        if command == "open_application":
            return self.applications.launch(
                arguments.get("app_name", "")
            )

        if command == "close_application":
            return self.applications.close(
                arguments.get("app_name", "")
            )

        func = TOOLS_REGISTRY.get(command)

        if func is None:
            return (
                f"Неизвестная системная "
                f"команда: {command}"
            )

        try:
            result = func(**arguments)

        except Exception as exc:
            return (
                f"Ошибка выполнения команды: "
                f"{exc}"
            )

        return str(result)
