from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SpotifyItem:
    """Найденная в каталоге Spotify композиция или плейлист."""

    uri: str
    name: str
    subtitle: str
    item_type: str

    def display_name(self) -> str:
        if self.subtitle:
            return f"{self.name} — {self.subtitle}"
        return self.name


class SpotifyController:
    """Управляет локальным Spotify через MPRIS и утилиту playerctl."""

    def __init__(
         self,
         config: dict[str, Any] | None = None,
     ) -> None:
         config = config or {}

         self.player = str(
             config.get("player", "spotify")
         )

         self.timeout_seconds = float(
             config.get(
                 "command_timeout_seconds",
                 5.0,
             )
         )

         self.my_music_playlist = str(
             config.get(
                 "my_music_playlist",
                 "",
             )
         )

         self.default_shuffle = bool(
             config.get(
                 "default_shuffle",
                 True,
             )
         )

    @property
    def playerctl_available(self) -> bool:
        return shutil.which("playerctl") is not None

    def is_available(self) -> bool:
        result, _ = self._run("status")
        return result is not None and result.returncode == 0

    def wait_until_available(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            if self.is_available():
                return True
            time.sleep(0.5)

        return self.is_available()

    def next_track(self) -> str:
        return self._transport("next", "Переключил на следующий трек.")

    def previous_track(self) -> str:
        return self._transport("previous", "Переключил на предыдущий трек.")

    def play_pause(self) -> str:
        return self._transport("play-pause", "Изменил состояние воспроизведения.")

    def play(self) -> str:
        return self._transport("play", "Продолжаю воспроизведение.")

    def pause(self) -> str:
        return self._transport("pause", "Воспроизведение приостановлено.")

    def current_track(self) -> str:
        result, error = self._run("status")

        if error:
            return error
        if result is None or result.returncode != 0:
            return self._player_error(result)

        status = result.stdout.strip()
        metadata, error = self._run(
            "metadata",
            "--format",
            "{{title}}\n{{artist}}\n{{album}}",
        )

        if error:
            return error
        if metadata is None or metadata.returncode != 0:
            return self._player_error(metadata)

        title, artist, album = self._metadata_parts(metadata.stdout)

        if not title:
            if status.lower() == "stopped":
                return "Spotify остановлен."
            return "Spotify не передал информацию о текущем треке."

        state = "играет" if status.lower() == "playing" else "на паузе"
        details = f"Сейчас {state}: {title}"

        if artist:
            details += f", {artist}"
        if album:
            details += f". Альбом: {album}"

        return f"{details}."

    def open_uri(self, value: str) -> str:
        uri = self.normalize_uri(value)

        if uri is None:
            return "Не удалось распознать ссылку или URI Spotify."

        result, error = self._run("open", uri)

        if error:
            return error
        if result is None or result.returncode != 0:
            return self._player_error(result)

        return "Отправил выбранную музыку в Spotify."

    def play_playlist(
        self,
        playlist_uri: str,
        shuffle: bool,
    ) -> str:
        uri = self.normalize_uri(playlist_uri)

        if uri is None:
            return "Не удалось распознать плейлист Spotify."

        if not uri.startswith("spotify:playlist:"):
            return "Указанный Spotify URI не является плейлистом."

        if not self.is_available():
            return (
                "Spotify не запущен или недоступен через MPRIS. "
                "Запустите Spotify и повторите команду."
            )

        # Сначала устанавливаем режим воспроизведения.
        shuffle_result, error = self._run(
            "shuffle",
            "On" if shuffle else "Off",
        )

        if error:
            return error

        if (
            shuffle_result is None
            or shuffle_result.returncode != 0
        ):
            return self._player_error(shuffle_result)

        # Затем открываем плейлист.
        open_result, error = self._run(
            "open",
            uri,
        )

        if error:
            return error

        if (
            open_result is None
            or open_result.returncode != 0
        ):
            return self._player_error(open_result)

        # Явно запускаем воспроизведение.
        play_result, error = self._run("play")

        if error:
            return error

        if (
            play_result is None
            or play_result.returncode != 0
        ):
            return self._player_error(play_result)

        if shuffle:
            return "Включил твою музыку в случайном порядке."

        return "Включил твою музыку по порядку."

    @staticmethod
    def normalize_uri(value: str) -> str | None:
        value = value.strip()
        uri_match = re.fullmatch(
            r"spotify:(track|playlist|album):([A-Za-z0-9]+)",
            value,
        )

        if uri_match:
            return value

        parsed = urllib.parse.urlparse(value)

        if parsed.scheme not in {"http", "https"}:
            return None
        if parsed.netloc.lower() not in {
            "open.spotify.com",
            "www.open.spotify.com",
        }:
            return None

        parts = [part for part in parsed.path.split("/") if part]

        for index, part in enumerate(parts[:-1]):
            if part in {"track", "playlist", "album"}:
                identifier = parts[index + 1]
                if re.fullmatch(r"[A-Za-z0-9]+", identifier):
                    return f"spotify:{part}:{identifier}"

        return None

    def _transport(self, action: str, confirmation: str) -> str:
        result, error = self._run(action)

        if error:
            return error
        if result is None or result.returncode != 0:
            return self._player_error(result)

        return confirmation

    def _run(
        self,
        *arguments: str,
    ) -> tuple[subprocess.CompletedProcess[str] | None, str | None]:
        if not self.playerctl_available:
            return None, (
                "Не найдена утилита playerctl. Установите её командой "
                "sudo apt install playerctl."
            )

        try:
            result = subprocess.run(
                ["playerctl", f"--player={self.player}", *arguments],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None, "Spotify не ответил вовремя."
        except OSError as exc:
            logger.exception("Не удалось запустить playerctl.")
            return None, f"Не удалось запустить playerctl: {exc}"

        return result, None

    @staticmethod
    def _metadata_parts(output: str) -> tuple[str, str, str]:
        parts = [line.strip() for line in output.splitlines()]
        parts.extend([""] * (3 - len(parts)))
        return parts[0], parts[1], parts[2]

    @staticmethod
    def _player_error(
        result: subprocess.CompletedProcess[str] | None,
    ) -> str:
        details = ""

        if result is not None:
            details = (result.stderr or result.stdout).strip()

        if "No players found" in details:
            return "Spotify не запущен или недоступен через MPRIS."

        if details:
            logger.warning("Ошибка playerctl: %s", details)

        return "Не удалось выполнить команду в Spotify."


class SpotifyCatalog:
    """Ищет треки, альбомы и плейлисты через Spotify Web API."""

    TOKEN_URL = "https://accounts.spotify.com/api/token"
    SEARCH_URL = "https://api.spotify.com/v1/search"

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

    def search(
        self,
        query: str,
        item_types: tuple[str, ...],
        limit: int = 5,
    ) -> tuple[list[SpotifyItem], str | None]:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

        if not client_id or not client_secret:
            return [], (
                "Для поиска в Spotify задайте переменные окружения "
                "SPOTIFY_CLIENT_ID и SPOTIFY_CLIENT_SECRET."
            )

        token, error = self._get_access_token(
            client_id,
            client_secret,
        )

        if error:
            return [], error
        if token is None:
            return [], "Не удалось авторизоваться в Spotify API."

        params = urllib.parse.urlencode(
            {
                "q": query,
                "type": ",".join(item_types),
                "limit": max(1, min(limit, 10)),
            }
        )
        request = urllib.request.Request(
            f"{self.SEARCH_URL}?{params}",
            headers={"Authorization": f"Bearer {token}"},
        )
        payload, error = self._request_json(request)

        if error:
            return [], error
        if payload is None:
            return [], "Spotify API вернул пустой ответ."

        items: list[SpotifyItem] = []

        for item_type in item_types:
            block = payload.get(f"{item_type}s", {})
            raw_items = block.get("items", [])

            if not isinstance(raw_items, list):
                continue

            for item in raw_items:
                spotify_item = self._parse_item(item, item_type)
                if spotify_item is not None:
                    items.append(spotify_item)

        if not items:
            return [], "В Spotify ничего не найдено."

        return items, None

    def _get_access_token(
        self,
        client_id: str,
        client_secret: str,
    ) -> tuple[str | None, str | None]:
        if (
            self._access_token is not None
            and time.monotonic() < self._access_token_expires_at
        ):
            return self._access_token, None

        credentials = base64.b64encode(
            f"{client_id}:{client_secret}".encode("utf-8")
        ).decode("ascii")
        request = urllib.request.Request(
            self.TOKEN_URL,
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        payload, error = self._request_json(request)

        if error:
            return None, error
        if payload is None:
            return None, "Spotify API вернул пустой ответ авторизации."

        token = payload.get("access_token")
        expires_in = payload.get("expires_in", 3600)

        if not isinstance(token, str):
            return None, "Spotify API не вернул токен доступа."

        self._access_token = token
        self._access_token_expires_at = (
            time.monotonic() + max(60, int(expires_in) - 60)
        )

        return token, None

    def _request_json(
        self,
        request: urllib.request.Request,
    ) -> tuple[dict[str, Any] | None, str | None]:
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.warning("Spotify API вернул HTTP %s: %s", exc.code, body)

            if exc.code == 401:
                return None, "Spotify API отклонил учётные данные приложения."
            if exc.code == 429:
                return None, "Spotify API временно ограничил количество запросов."

            return None, f"Spotify API вернул ошибку {exc.code}."
        except urllib.error.URLError as exc:
            logger.warning("Не удалось подключиться к Spotify API: %s", exc.reason)
            return None, "Не удалось подключиться к Spotify API."
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception("Некорректный ответ Spotify API.")
            return None, f"Не удалось обработать ответ Spotify API: {exc}"

        if not isinstance(payload, dict):
            return None, "Spotify API вернул некорректный ответ."

        return payload, None

    @staticmethod
    def _parse_item(
        item: Any,
        item_type: str,
    ) -> SpotifyItem | None:
        if not isinstance(item, dict):
            return None

        uri = item.get("uri")
        name = item.get("name")

        if not isinstance(uri, str) or not isinstance(name, str):
            return None

        subtitle = ""

        if item_type == "track":
            artists = item.get("artists", [])
            if isinstance(artists, list):
                subtitle = ", ".join(
                    artist["name"]
                    for artist in artists
                    if isinstance(artist, dict)
                    and isinstance(artist.get("name"), str)
                )
        elif item_type == "playlist":
            owner = item.get("owner", {})
            if isinstance(owner, dict) and isinstance(owner.get("display_name"), str):
                subtitle = owner["display_name"]
        elif item_type == "album":
            artists = item.get("artists", [])
            if isinstance(artists, list):
                subtitle = ", ".join(
                    artist["name"]
                    for artist in artists
                    if isinstance(artist, dict)
                    and isinstance(artist.get("name"), str)
                )

        return SpotifyItem(
            uri=uri,
            name=name,
            subtitle=subtitle,
            item_type=item_type,
        )
