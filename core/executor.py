from __future__ import annotations

import logging
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

        if command == "open_application":
            return self.applications.launch(
                arguments.get("app_name", "")
            )

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
