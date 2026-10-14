from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.applications import ApplicationResolver
from core.spotify import SpotifyController
from tools.registry import TOOLS_REGISTRY


logger = logging.getLogger(__name__)


class CommandExecutor:
    """Выполняет локальные команды без LLM."""

    def __init__(
        self,
        spotify_config: dict[str, Any] | None = None,
    ) -> None:
        self.applications = ApplicationResolver()
        self.spotify = SpotifyController(spotify_config)

    def execute(
        self,
        command: str,
        arguments: dict[str, Any],
    ) -> str:
        logger.info("Выполнение команды: %s.", command)
        logger.debug(
            "Аргументы команды %s: %s",
            command,
            arguments,
        )

        if command == "create_note":
            return self._create_note(arguments.get("title", ""))

        if command == "open_application":
            app_name = arguments.get("app_name", "")
            if self.applications._resolve_alias(app_name) == "marktext":
                return self._open_blank_note()
            return self.applications.launch(app_name)

        if command == "close_application":
            return self.applications.close(
                arguments.get("app_name", "")
            )

        if command == "spotify_next":
            return self.spotify.next_track()

        if command == "spotify_previous":
            return self.spotify.previous_track()

        if command == "spotify_play_pause":
            return self.spotify.play_pause()

        if command == "spotify_play":
            return self.spotify.play()

        if command == "spotify_pause":
            return self.spotify.pause()

        if command == "spotify_current_track":
            return self.spotify.current_track()

        if command == "spotify_my_music":
            shuffle = arguments.get("shuffle")

            if shuffle is None:
                shuffle = self.spotify.default_shuffle

            return self.spotify.play_playlist(
                self.spotify.my_music_playlist,
                shuffle=bool(shuffle),
            )

        function = TOOLS_REGISTRY.get(command)

        if function is None:
            return (
                "Неизвестная системная команда: "
                f"{command}"
            )

        try:
            return str(function(**arguments))
        except Exception as exc:
            logger.exception(
                "Ошибка выполнения команды: %s",
                command,
            )
            return f"Ошибка выполнения команды: {exc}"

    @staticmethod
    def _launch_marktext(note_path: Path) -> str | None:
        """Открывает конкретный Markdown-файл в MarkText."""
        if shutil.which("marktext"):
            command = ["marktext", str(note_path)]
        elif shutil.which("flatpak"):
            app_id = "com.github.marktext.marktext"
            check = subprocess.run(
                ["flatpak", "info", app_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if check.returncode:
                return "MarkText не найден среди установленных приложений."
            command = ["flatpak", "run", app_id, str(note_path)]
        else:
            return "Не найдена команда marktext или flatpak."

        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            logger.exception("Не удалось открыть файл в MarkText.")
            return f"Не удалось запустить MarkText: {exc}"
        return None

    @staticmethod
    def _open_blank_note() -> str:
        """Создаёт отдельный пустой Markdown-файл и открывает его."""
        notes_dir = Path("/home/vanyusha/Notes")
        try:
            notes_dir.mkdir(parents=True, exist_ok=True)
            note_path = notes_dir / "Новая заметка.md"
            index = 2
            while note_path.exists():
                note_path = notes_dir / f"Новая заметка {index}.md"
                index += 1
            note_path.write_text("", encoding="utf-8")
        except OSError as exc:
            logger.exception("Не удалось создать пустую заметку.")
            return f"Не удалось создать пустую заметку: {exc}"

        error = CommandExecutor._launch_marktext(note_path)
        if error:
            return f"Файл создан: {note_path}. {error}"
        return f"Открыта пустая заметка в MarkText: {note_path}"

    @staticmethod
    def _create_note(title: str) -> str:
        title = title.strip().strip(chr(34) + "'«»")
        title = re.sub(r'[\x00-\x1f/\\\\:*?<>|]', "-", title)
        title = re.sub(r"\s+", " ", title).strip(" .")
        if not title:
            return "Название заметки не может быть пустым."

        notes_dir = Path("/home/vanyusha/Notes")
        try:
            notes_dir.mkdir(parents=True, exist_ok=True)
            note_path = notes_dir / f"{title}.md"
            if note_path.exists():
                return f"Заметка уже существует: {note_path}"
            note_path.write_text(f"# {title}\n\n", encoding="utf-8")
        except OSError as exc:
            logger.exception("Не удалось создать заметку.")
            return f"Ошибка создания заметки: {exc}"

        error = CommandExecutor._launch_marktext(note_path)
        if error:
            return f"Заметка создана: {note_path}. {error}"
        return f"Создана заметка и открыта в MarkText: {note_path}"
