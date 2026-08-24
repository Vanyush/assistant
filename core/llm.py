import json
import re
import ollama
from tools.registry import TOOLS_REGISTRY, TOOL_SCHEMAS
import tools.system 

class Brain:
    def __init__(self, model_name: str, system_prompt_path: str):
        self.model_name = model_name
        self.messages = []
        
        with open(system_prompt_path, "r", encoding="utf-8") as f:
            self.messages.append({"role": "system", "content": f.read()})

    def _extract_qwen_tool_call(self, text: str):
        """Агрессивный поиск JSON-вызова функции в любом текстовом мусоре"""
        # Ищем начало объекта { и ключевые слова "name" и "arguments".
        # Затем берем ВСЁ до последней фигурной скобки } в тексте.
        match = re.search(r'(\{.*?"name"\s*:\s*".*?".*?"arguments"\s*:.*\})', text, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                # Очищаем строку от возможных невидимых спецсимволов перед парсингом
                clean_json = ''.join(char for char in json_str if char.isprintable() or char in '\n\r\t')
                data = json.loads(clean_json)
                if 'name' in data and 'arguments' in data:
                    return data
            except json.JSONDecodeError as e:
                # Если парсер упал, возможно модель забыла закрывающую скобку (бывает редко)
                # или добавила лишний текст внутри фигурных скобок. 
                # Попробуем добавить скобку принудительно, если ее нет.
                if not clean_json.strip().endswith('}'):
                     try:
                         data = json.loads(clean_json + '}')
                         if 'name' in data and 'arguments' in data:
                             return data
                     except json.JSONDecodeError:
                         pass
                print(f"[DEBUG] Ошибка JSON парсинга: {e}. Строка: {clean_json}")
                return None
        return None

    def _is_system_command(self, text: str) -> bool:
        """Определяет, является ли запрос пользователя командой к системе"""
        text = text.lower()
        trigger_words = [
            "громкост", "тише", "громче", "звук",
            "состояние", "статус", "температур", "нагрузк", "процессор", "памят", "систем",
            "включи", "выключи", "свет", "умный дом", 'открой', 'запусти', 'закрой'
        ]
        return any(word in text for word in trigger_words)

    def process_input(self, user_text: str) -> str:
        # Если пользователь просит выполнить системную команду,
        # мы радикально забываем предыдущий диалог, оставляя только промпт.
        # Это ЗАСТАВИТ модель обрабатывать запрос как абсолютно новый и вызывать функцию.
        if self._is_system_command(user_text):
             print("[DEBUG] Обнаружена системная команда. Очистка контекста...")
             self.messages = [self.messages[0]] # Оставляем только system prompt
        else:
             # Если это обычный разговор, сохраняем последние 6 сообщений
             if len(self.messages) > 7:
                 self.messages = [self.messages[0]] + self.messages[-6:]

        self.messages.append({"role": "user", "content": user_text})

        # Шаг 1: Запрос к модели
        response = ollama.chat(
            model=self.model_name,
            messages=self.messages,
            tools=TOOL_SCHEMAS
        )

        message = response.get('message', {})
        self.messages.append(message)
        content = message.get('content', '')

        # Шаг 2: Проверка на Tool Call
        tool_call_data = None
        
        if message.get('tool_calls'):
             call = message['tool_calls'][0]['function']
             tool_call_data = {"name": call['name'], "arguments": call['arguments']}
        elif content and '"name"' in content and '"arguments"' in content:
             tool_call_data = self._extract_qwen_tool_call(content)

        # Шаг 3: Выполнение функции
        if tool_call_data:
            func_name = tool_call_data.get('name')
            args = tool_call_data.get('arguments', {})
            
            print(f"[SYSTEM] Джарвис выполняет команду: {func_name}({args})")
            
            if func_name in TOOLS_REGISTRY:
                func = TOOLS_REGISTRY[func_name]
                try:
                    result = func(**args)
                except Exception as e:
                    result = f"Ошибка выполнения: {e}"
                    
                self.messages.append({
                    "role": "user", 
                    "content": f"Результат выполнения функции {func_name}: {result}. Ответь пользователю на основе этих данных кратко."
                })

                # Шаг 4: Получение финального ответа
                final_response = ollama.chat(
                    model=self.model_name,
                    messages=self.messages
                )
                final_message = final_response['message']
                self.messages.append(final_message)
                return final_message.get('content', '')

        return content