from core.applications import ApplicationResolver


resolver = ApplicationResolver()


queries = [
    "spotify",
    "спотифай",

    "telegram",
    "телеграм",
    "телега",

    "chrome",
    "хром",

    "firefox",
    "фаерфокс",

    "браузер",

    "блокнот",
    "текстовый редактор",

    "файлы",
    "проводник",
]


for query in queries:
    app = resolver.resolve(query)

    print()
    print("=" * 70)
    print(f"Запрос: {query}")

    if app is None:
        print("НЕ НАЙДЕНО")
        continue

    print(f"Name:       {app.name}")
    print(f"Generic:    {app.generic_name}")
    print(f"Desktop:    {app.desktop_file}")
    print(f"Exec:       {app.exec_command}")
