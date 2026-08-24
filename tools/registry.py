import inspect
from typing import get_type_hints

TOOLS_REGISTRY = {}
TOOL_SCHEMAS = []

def map_python_type_to_json(py_type):
    if py_type == int: return "integer"
    if py_type == float: return "number"
    if py_type == bool: return "boolean"
    return "string"

def register_tool(description: str):
    """Декоратор для автоматической регистрации функции как инструмента для LLM"""
    def decorator(func):
        sig = inspect.signature(func)
        hints = get_type_hints(func)
        
        properties = {}
        required = []
        
        for name, param in sig.parameters.items():
            param_type = hints.get(name, str)
            properties[name] = {
                "type": map_python_type_to_json(param_type),
                "description": f"Параметр {name}"
            }
            if param.default == inspect.Parameter.empty:
                required.append(name)
                
        schema = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        TOOLS_REGISTRY[func.__name__] = func
        TOOL_SCHEMAS.append(schema)
        return func
    return decorator