#!/usr/bin/env sh

set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$PROJECT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Ошибка: Python 3 не найден."
    exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[SETUP] Создание виртуального окружения..."

    "$PYTHON_BIN" -m venv "$VENV_DIR"

    echo "[SETUP] Обновление pip..."
    "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel

    echo "[SETUP] Установка зависимостей..."
    "$VENV_DIR/bin/python" -m pip install -r requirements.txt

    echo "[SETUP] Готово."
fi

if [ ! -f "config/config.yaml" ]; then
    echo "Ошибка: не найден config/config.yaml."
    exit 1
fi

echo "[SYSTEM] Запуск ассистента..."
exec "$VENV_DIR/bin/python" main.py
