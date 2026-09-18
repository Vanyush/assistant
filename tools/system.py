import psutil
import subprocess
from tools.registry import register_tool
import shutil

@register_tool(
    "Запустить программу. В аргумент app_name передавай ТОЛЬКО ОДНО из этих слов на русском языке: "
    "браузер, хром, телеграм, терминал, блокнот, файлы. Никаких английских названий процессов!"
)
def open_application(app_name: str) -> str:
    """Запускает приложение в Linux Mint с точным маппингом синонимов."""
    app_name_clean = app_name.lower().strip()

    # Словарь синонимов (что бы ни прислала модель, привязываем к четким ключам)
    synonyms = {
        "блокнот": "блокнот",
        "текстовый редактор": "блокнот",
        "редактор": "блокнот",
        "нотпад": "блокнот",
        "браузер": "браузер",
        "интернет": "браузер",
        "хром": "хром",
        "chrome": "хром",
        "телеграм": "телеграм",
        "телега": "телеграм",
        "telegram": "телеграм",
        "терминал": "терминал",
        "консоль": "терминал",
        "файлы": "файлы",
        "проводник": "файлы",
        "папки": "файлы"
    }

    # Если модель прислала что-то с иероглифами или мусором, но мы можем распознать суть
    for key, normalized in synonyms.items():
        if key in app_name_clean:
            app_name_clean = normalized
            break

    # Расширенный словарь возможных названий и их альтернатив в Linux Mint
    app_mapping = {
        "браузер": ["firefox", "google-chrome", "chromium-browser", "brave-browser"],
        "хром": ["google-chrome", "chromium-browser", "chromium"],
        "телеграм": ["telegram-desktop", "telegram"],
        "терминал": ["gnome-terminal", "tilix", "terminator", "konsole", "x-terminal-emulator"],
        "блокнот": ["xed", "gedit", "mousepad", "gnome-text-editor", "pluma"],
        "файлы": ["nemo", "nautilus", "dolphin", "thunar"]
    }

    # Получаем список вариантов для проверки
    candidates = app_mapping.get(app_name_clean, [app_name_clean])

    # Ищем первый попавшийся бинарник, который реально существует в системе
    executable = None
    for candidate in candidates:
        if shutil.which(candidate):
            executable = candidate
            break

    if not executable:
        return f"Не удалось найти приложение '{app_name}' в системе. Проверьте, установлено ли оно."

    try:
        subprocess.Popen(
            [executable],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return f"Приложение {app_name} успешно запущено."
    except Exception as e:
        return f"Ошибка при запуске приложения: {e}"

@register_tool(
    "Закрыть программу. В аргумент app_name передавай ТОЛЬКО ОДНО из этих слов на русском языке: "
    "браузер, хром, телеграм, терминал, блокнот, файлы."
)
def close_application(app_name: str) -> str:
    """Закрывает процесс приложения в Linux Mint с учетом альтернативных имен."""
    app_name_clean = app_name.lower().strip()

    # Словарь соответствия пользовательских имен реальным именам процессов в ОС
    process_mapping = {
        "браузер": ["firefox", "chrome", "chromium", "brave"],
        "хром": ["google-chrome", "chromium-browser", "chrome"],
        "chrome": ["google-chrome", "chromium-browser", "chrome"],
        "телеграм": ["telegram-desktop", "telegram"],
        "telegram": ["telegram-desktop", "telegram"],
        "терминал": ["gnome-terminal", "tilix", "terminator", "konsole"],
        "блокнот": ["xed", "gedit", "mousepad", "gnome-text-editor", "pluma"],
        "текстовый редактор": ["xed", "gedit", "mousepad", "gnome-text-editor", "pluma"],
        "файлы": ["nemo", "nautilus", "dolphin", "thunar"]
    }

    # Получаем список возможных процессов для закрытия
    processes = process_mapping.get(app_name_clean, [app_name_clean])

    closed_any = False
    for proc in processes:
        try:
            result = subprocess.run(
                ["pkill", "-f", proc],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                closed_any = True
        except Exception:
            pass

    if closed_any:
        return f"Приложение {app_name} успешно закрыто."
    else:
        return f"Не удалось найти запущенный процесс для '{app_name}'."

@register_tool("Получить текущую загрузку системы: температуру, CPU и RAM")
def get_system_status() -> str:
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent

    # Попытка получить температуру (на Ryzen обычно k10temp)
    temps = psutil.sensors_temperatures()
    temp_str = ""
    if 'k10temp' in temps:
        temp_str = f"Температура процессора: {temps['k10temp'][0].current:.0f}°C. "

    return f"{temp_str}Загрузка CPU: {cpu}%. Использование оперативной памяти: {ram}%."

@register_tool("Изменить общую громкость системы Linux Mint")
def set_volume(level: int) -> str:
    # Используем amixer (стандартная утилита в Linux Mint/Ubuntu)
    level = max(0, min(100, level))
    subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"], capture_output=True)
    return f"Громкость системы установлена на {level}%."

@register_tool("Увеличить громкость системы Linux Mint")
def volume_up(step: int = 10) -> str:
    step = max(1, min(100, step))

    try:
        result = subprocess.run(
            [
                "pactl",
                "set-sink-volume",
                "@DEFAULT_SINK@",
                f"+{step}%",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        return f"Громкость увеличена на {step}%."

    except subprocess.CalledProcessError as e:
        return f"Ошибка изменения громкости: {e.stderr.strip()}"


@register_tool("Уменьшить громкость системы Linux Mint")
def volume_down(step: int = 10) -> str:
    step = max(1, min(100, step))

    try:
        result = subprocess.run(
            [
                "pactl",
                "set-sink-volume",
                "@DEFAULT_SINK@",
                f"-{step}%",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        return f"Громкость уменьшена на {step}%."

    except subprocess.CalledProcessError as e:
        return f"Ошибка изменения громкости: {e.stderr.strip()}"

@register_tool("Узнать текущий уровень громкости системы")
def get_volume() -> str:
    # Запускаем команду pactl для получения текущей громкости
    try:
        result = subprocess.run(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
            capture_output=True, text=True, check=True
        )
        # Ищем процентное значение в выводе (например, "Volume: front-left: 54067 /  82% / -5.16 dB...")
        output = result.stdout
        import re
        match = re.search(r'(\d+)%', output)
        if match:
            return f"Текущая громкость системы: {match.group(1)}%"
        return "Не удалось определить текущую громкость."
    except Exception as e:
        return f"Ошибка при получении громкости: {e}"
