import asyncio
import yaml
from core.llm import Brain

async def main():
    print("Загрузка конфигурации...")
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print(f"Инициализация мозга ({config['llm']['model']})...")
    brain = Brain(
        model_name=config['llm']['model'],
        system_prompt_path="config/system_prompt.txt"
    )

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

            response = brain.process_input(user_input)
            print(f"\nДжарвис: {response}")
            
            # TODO: Отправить response в модуль TTS (Piper) для озвучки

        except KeyboardInterrupt:
            break

    print("\nОтключение систем...")

if __name__ == "__main__":
    asyncio.run(main())