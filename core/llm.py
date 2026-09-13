from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from tools.registry import TOOLS_REGISTRY, TOOL_SCHEMAS
import tools.system


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

        with open(system_prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()

        self.messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

    @staticmethod
    def _extract_qwen_tool_call(text: str) -> dict[str, Any] | None:
        """Пытается извлечь JSON-вызов инструмента из текстового ответа модели."""

        match = re.search(
            r'(\{.*?"name"\s*:\s*".*?".*?"arguments"\s*:.*\})',
            text,
            re.DOTALL,
        )

        if not match:
            return None

        json_str = match.group(1)

        clean_json = "".join(
            char
            for char in json_str
            if char.isprintable() or char in "\n\r\t"
        )

        try:
            data = json.loads(clean_json)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        if "name" not in data or "arguments" not in data:
            return None

        return data

    @staticmethod
    def _is_system_command(text: str) -> bool:
        """Пока оставляем старую проверку до появления отдельного Router."""

        text = text.lower()

        trigger_words = [
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
        ]

        return any(word in text for word in trigger_words)

    def _trim_history(self) -> None:
        """Оставляем системный prompt и последние сообщения."""

        if len(self.messages) > 7:
            self.messages = [self.messages[0]] + self.messages[-6:]

    def _chat(self) -> Any:
        """Отправляет текущий context в LM Studio."""

        return self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            tools=TOOL_SCHEMAS,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def process_input(self, user_text: str) -> str:
        """Обрабатывает пользовательский запрос через локальную LLM."""

        if self._is_system_command(user_text):
            print("[DEBUG] Обнаружена системная команда.")
            self.messages = [self.messages[0]]
        else:
            self._trim_history()

        self.messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        print("[LLM] Запрос в LM Studio...")

        response = self._chat()

        message = response.choices[0].message

        message_dict: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }

        tool_calls = getattr(message, "tool_calls", None)

        if tool_calls:
            message_dict["tool_calls"] = []

            for call in tool_calls:
                message_dict["tool_calls"].append(
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                )

        self.messages.append(message_dict)

        content = message.content or ""

        # Обычный текстовый ответ
        if not tool_calls:
            parsed_call = None

            if '"name"' in content and '"arguments"' in content:
                parsed_call = self._extract_qwen_tool_call(content)

            if parsed_call is None:
                return content

            tool_name = parsed_call["name"]
            args = parsed_call.get("arguments", {})

            return self._execute_tool(tool_name, args)

        # Нормальный OpenAI-compatible tool call
        call = tool_calls[0]

        func_name = call.function.name
        raw_args = call.function.arguments

        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}

        return self._execute_tool(func_name, args, call.id)

    def _execute_tool(
        self,
        func_name: str,
        args: dict[str, Any],
        tool_call_id: str | None = None,
    ) -> str:
        """Выполняет tool и при необходимости получает финальный ответ LLM."""

        print(f"[SYSTEM] Джарвис выполняет: {func_name}({args})")

        if func_name not in TOOLS_REGISTRY:
            return f"Неизвестная команда: {func_name}"

        func = TOOLS_REGISTRY[func_name]

        try:
            result = func(**args)
        except Exception as exc:
            result = f"Ошибка выполнения: {exc}"

        # Пока сохраняем текущую архитектуру:
        # результат команды возвращается обратно в LLM
        # для формирования естественного ответа.
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
                        f"Результат выполнения функции {func_name}: "
                        f"{result}. Ответь пользователю кратко."
                    ),
                }
            )

        final_response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        final_message = final_response.choices[0].message
        final_content = final_message.content or ""

        self.messages.append(
            {
                "role": "assistant",
                "content": final_content,
            }
        )

        return final_content
