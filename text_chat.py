import asyncio
import yaml
from core.llm import Brain
from core.router import CommandRouter
from core.executor import CommandExecutor

async def main():
    print("Загрузка конфигурации...")
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print(f"Инициализация мозга ({config['llm']['model']})...")
    brain = Brain(
        model_name=config["llm"]["model"],
        system_prompt_path="config/system_prompt.txt",
        base_url=config["llm"]["host"],
        temperature=config["llm"].get("temperature", 0.2),
        max_tokens=config["llm"].get("max_tokens", 256),
    )

    router = CommandRouter()
    executor = CommandExecutor()

    print("\n[Система готова. Для выхода введите 'exit']")
    print("-" * 50)

    # TODO: Заменить цикл input() на захват аудио (Wake Word -> STT)
    while True:
        try:
            user_input = input("\nВы: ")
            if user_input.lower() in ['exit', 'выход', 'quit']:
                break

            if not user_input.strip():
                continue

            route = router.route(user_input)

            if route is not None:
                print(
                    f"[ROUTER] Системная команда: "
                    f"{route.command}"
                )

                response = executor.execute(
                    route.command,
                    route.arguments,
                )
            else:
                print("[ROUTER] Обычный запрос → LLM")

                response = brain.process_input(user_input)
            print(f"\nДжарвис: {response}")

            # TODO: Отправить response в модуль TTS (Piper) для озвучки

        except KeyboardInterrupt:
            break

    print("\nОтключение систем...")

if __name__ == "__main__":
    asyncio.run(main())
