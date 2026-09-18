from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

from tools.registry import TOOLS_REGISTRY, TOOL_SCHEMAS
import tools.system as _system_tools


logger = logging.getLogger(__name__)


class Brain:
    """Интерфейс локальной LLM через OpenAI-compatible API."""

    def __init__(
        self,
        model_name: str,
        system_prompt_path: str,
        base_url: str = "http://localhost:1234/v1",
        temperature: float = 0.2,
        max_tokens: int = 256,
    ) -> None:
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.client = OpenAI(
            base_url=base_url,
            api_key="lm-studio",
        )

        with open(
            system_prompt_path,
            "r",
            encoding="utf-8",
        ) as prompt_file:
            system_prompt = prompt_file.read()

        self.messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        logger.info(
            "LLM подключена: %s.",
            model_name,
        )

    @staticmethod
    def _extract_qwen_tool_call(
        text: str,
    ) -> dict[str, Any] | None:
        match = re.search(
            r'(\{.*?"name"\s*:\s*".*?".*?"arguments"\s*:.*\})',
            text,
            re.DOTALL,
        )

        if not match:
            return None

        json_text = "".join(
            character
            for character in match.group(1)
            if character.isprintable()
            or character in "\n\r\t"
        )

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        if "name" not in data or "arguments" not in data:
            return None

        return data

    @staticmethod
    def _is_system_command(text: str) -> bool:
        trigger_words = (
            "громкост",
            "тише",
            "громче",
            "звук",
            "состояние",
            "статус",
            "температур",
            "нагрузк",
            "процессор",
            "памят",
            "систем",
            "включи",
            "выключи",
            "свет",
            "умный дом",
            "открой",
            "запусти",
            "закрой",
        )

        normalized_text = text.lower()

        return any(
            word in normalized_text
            for word in trigger_words
        )

    def _trim_history(self) -> None:
        if len(self.messages) > 7:
            self.messages = [
                self.messages[0],
                *self.messages[-6:],
            ]

    def _chat(self) -> Any:
        return self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            tools=TOOL_SCHEMAS,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def process_input(self, user_text: str) -> str:
        if self._is_system_command(user_text):
            self.messages = [self.messages[0]]
            logger.debug(
                "Контекст очищен для системной команды."
            )
        else:
            self._trim_history()

        self.messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        logger.info("LLM обрабатывает запрос.")

        response = self._chat()
        message = response.choices[0].message

        message_dict: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }

        tool_calls = getattr(message, "tool_calls", None)

        if tool_calls:
            message_dict["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in tool_calls
            ]

        self.messages.append(message_dict)

        content = message.content or ""

        if not tool_calls:
            parsed_call = None

            if '"name"' in content and '"arguments"' in content:
                parsed_call = self._extract_qwen_tool_call(
                    content
                )

            if parsed_call is None:
                return content

            return self._execute_tool(
                parsed_call["name"],
                parsed_call.get("arguments", {}),
            )

        call = tool_calls[0]

        try:
            arguments = json.loads(
                call.function.arguments
            )
        except json.JSONDecodeError:
            arguments = {}

        return self._execute_tool(
            call.function.name,
            arguments,
            call.id,
        )

    def _execute_tool(
        self,
        function_name: str,
        arguments: dict[str, Any],
        tool_call_id: str | None = None,
    ) -> str:
        logger.info(
            "LLM выполняет инструмент: %s.",
            function_name,
        )
        logger.debug(
            "Аргументы инструмента %s: %s",
            function_name,
            arguments,
        )

        function = TOOLS_REGISTRY.get(function_name)

        if function is None:
            return f"Неизвестная команда: {function_name}"

        try:
            result = function(**arguments)
        except Exception as exc:
            logger.exception(
                "Ошибка инструмента: %s",
                function_name,
            )
            result = f"Ошибка выполнения: {exc}"

        if tool_call_id is not None:
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": str(result),
                }
            )
        else:
            self.messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Результат функции {function_name}: "
                        f"{result}. Ответь кратко."
                    ),
                }
            )

        final_response = (
            self.client.chat.completions.create(
                model=self.model_name,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        )

        final_content = (
            final_response.choices[0].message.content
            or ""
        )

        self.messages.append(
            {
                "role": "assistant",
                "content": final_content,
            }
        )

        return final_content
