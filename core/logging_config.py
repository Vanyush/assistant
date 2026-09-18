from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


DEFAULT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _get_level(value: Any, default: int) -> int:
    if not isinstance(value, str):
        return default

    return getattr(logging, value.upper(), default)


def configure_logging(config: dict[str, Any] | None = None) -> None:
    """Настраивает краткий вывод в консоль и полный debug-лог в файл."""
    config = config or {}

    console_level = _get_level(
        config.get("console_level"),
        logging.INFO,
    )
    file_level = _get_level(
        config.get("file_level"),
        logging.DEBUG,
    )
    log_path = Path(
        config.get("file", "logs/assistant.log")
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        DEFAULT_FORMAT,
        datefmt=DATE_FORMAT,
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[console_handler, file_handler],
        force=True,
    )

    logging.captureWarnings(True)

    for library_name in (
        "httpx",
        "httpcore",
        "openai",
        "faster_whisper",
        "ctranslate2",
        "urllib3",
    ):
        logging.getLogger(library_name).setLevel(
            logging.WARNING
        )
