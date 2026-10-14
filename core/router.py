from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Route:
    """Результат разбора пользовательской команды."""

    command: str
    arguments: dict[str, Any]


class CommandRouter:
    """
    Определяет простые системные команды без LLM.

    None означает:
    запрос не является известной локальной командой
    и должен быть передан в LLM.
    """

    def route(self, text: str) -> Route | None:
        text = self._normalize(text)

        if not text:
            return None

        route = self._route_create_note(text)
        if route is not None:
            return route

        route = self._route_volume(text)
        if route is not None:
            return route

        route = self._route_system_status(text)
        if route is not None:
            return route

        route = self._route_spotify_my_music(text)
        if route is not None:
            return route

        route = self._route_open_application(text)
        if route is not None:
            return route

        route = self._route_close_application(text)
        if route is not None:
            return route

        route = self._route_spotify(text)
        if route is not None:
            return route

        return None

    @staticmethod
    def _route_create_note(text: str) -> Route | None:
        match = re.fullmatch(r'(?:создай|создать)\s+заметку\s+["«]?(.+?)["»]?', text)
        if not match:
            return None
        title = match.group(1).strip().strip(chr(34) + "'«»")
        if not title:
            return None
        return Route(command="create_note", arguments={"title": title})

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.strip().lower()

        text = text.replace("ё", "е")

        text = re.sub(r"\s+", " ", text)

        text = text.rstrip("!?.,:;")

        return text.strip()


    # ------------------------------------------------------------------
    # VOLUME
    # ------------------------------------------------------------------

    def _route_volume(self, text: str) -> Route | None:

        if text in {
            "громкость",
            "какая громкость",
            "текущая громкость",
            "уровень громкости",
            "какой уровень громкости",
            "сколько громкость",
        }:
            return Route(
                command="get_volume",
                arguments={},
            )

        match = re.fullmatch(
            r"(?:установи\s+)?громкость\s+(\d{1,3})",
            text,
        )

        if match:
            level = int(match.group(1))

            level = max(
                0,
                min(100, level),
            )

            return Route(
                command="set_volume",
                arguments={
                    "level": level,
                },
            )

        if text in {
            "громче",
            "сделай громче",
            "прибавь звук",
            "увеличь громкость",
            "увеличь звук",
        }:
            return Route(
                command="volume_up",
                arguments={
                    "step": 10,
                },
            )

        if text in {
            "тише",
            "сделай тише",
            "убавь звук",
            "уменьши громкость",
            "уменьши звук",
        }:
            return Route(
                command="volume_down",
                arguments={
                    "step": 10,
                },
            )

        return None


    # ------------------------------------------------------------------
    # SYSTEM STATUS
    # ------------------------------------------------------------------

    def _route_system_status(
        self,
        text: str,
    ) -> Route | None:

        if text in {
            "система",
            "статус",
            "состояние",
            "статус системы",
            "состояние системы",
            "системная информация",
            "информация о системе",
            "что с системой",
            "как система",
        }:
            return Route(
                command="get_system_status",
                arguments={},
            )

        status_phrases = (
            "температура процессора",
            "температура cpu",
            "температура цпу",
            "температура проца",
            "загрузка процессора",
            "загрузка cpu",
            "загрузка цпу",
            "использование процессора",
            "использование cpu",
            "использование цпу",
            "сколько оперативной памяти",
            "использование оперативной памяти",
            "использование озу",
            "сколько озу",
            "занято озу",
        )

        if any(
            phrase in text
            for phrase in status_phrases
        ):
            return Route(
                command="get_system_status",
                arguments={},
            )

        return None


    # ------------------------------------------------------------------
    # OPEN APPLICATION
    # ------------------------------------------------------------------

    def _route_open_application(
        self,
        text: str,
    ) -> Route | None:

        match = re.fullmatch(
            r"(?:"
            r"открой|"
            r"открыть|"
            r"запусти|"
            r"запустить|"
            r"запуск"
            r")"
            r"(?:\s+приложение)?"
            r"\s+(.+)",
            text,
        )

        if not match:
            return None

        app_name = match.group(1).strip()

        if not app_name:
            return None

        return Route(
            command="open_application",
            arguments={
                "app_name": app_name,
            },
        )


    # ------------------------------------------------------------------
    # SPOTIFY
    # ------------------------------------------------------------------

    def _route_spotify(self, text: str) -> Route | None:
        if text in {
            "следующий трек",
            "следующая песня",
            "дальше",
            "переключи трек",
            "переключи песню",
            "включи следующий трек",
            "включи следующую песню",
        }:
            return Route(
                command="spotify_next",
                arguments={},
            )

        if text in {
            "предыдущий трек",
            "предыдущая песня",
            "назад",
            "переключи на предыдущий трек",
            "включи предыдущий трек",
            "включи предыдущую песню",
        }:
            return Route(
                command="spotify_previous",
                arguments={},
            )

        if text in {
            "пауза",
            "поставь на паузу",
            "поставь музыку на паузу",
            "поставь воспроизведение на паузу",
            "приостанови музыку",
        }:
            return Route(
                command="spotify_pause",
                arguments={},
            )

        if text in {
            "продолжи",
            "продолжи музыку",
            "продолжи воспроизведение",
            "возобнови музыку",
            "возобнови воспроизведение",
            "продолжить",
            "возобнови",
            "продолжим",
        }:
            return Route(
                command="spotify_play",
                arguments={},
            )

        if text in {
            "пауза или продолжи",
            "пауза продолжи",
            "переключи воспроизведение",
        }:
            return Route(
                command="spotify_play_pause",
                arguments={},
            )

        if text in {
            "что играет",
            "что сейчас играет",
            "какая песня играет",
            "какой трек играет",
            "название песни",
            "название текущего трека",
        }:
            return Route(
                command="spotify_current_track",
                arguments={},
            )

        return None


    # ------------------------------------------------------------------
    # SPOTIFY — MY MUSIC
    # ------------------------------------------------------------------

    def _route_spotify_my_music(
        self,
        text: str,
    ) -> Route | None:
        """
        Включает заранее заданный пользовательский плейлист.

        Поддерживаемые варианты:

        "включи мою музыку"
        "включить мою музыку"
        "запусти мою музыку"
        "поставь мою музыку"

        Случайный порядок:

        "включи мою музыку случайно"
        "включи мою музыку в случайном порядке"
        "включи мою музыку в случайном режиме"
        "включи мою музыку вразнобой"
        "включи мою музыку с перемешиванием"

        Последовательный порядок:

        "включи мою музыку по порядку"
        "включи мою музыку по очереди"
        "включи мою музыку последовательно"
        "включи мою музыку в обычном порядке"
        "включи мою музыку без перемешивания"
        """

        match = re.fullmatch(
            r"(?:"
            r"включи|"
            r"включить|"
            r"запусти|"
            r"запустить|"
            r"поставь|"
            r"поставить"
            r")"
            r"\s+"
            r"(?:"
            r"мою музыку|"
            r"моя музыка|"
            r"свою музыку|"
            r"своя музыка"
            r")"
            r"(?:\s+(.+))?",
            text,
        )

        if not match:
            return None

        mode = (match.group(1) or "").strip()

        # --------------------------------------------------------------
        # RANDOM
        # --------------------------------------------------------------

        if any(
            phrase in mode
            for phrase in (
                "случайн",
                "вразнобой",
                "рандом",
                "перемеш",
                "вперемешку",
            )
        ):
            shuffle = True

        # --------------------------------------------------------------
        # SEQUENTIAL
        # --------------------------------------------------------------

        elif any(
            phrase in mode
            for phrase in (
                "по порядку",
                "по очереди",
                "последовательно",
                "упорядоченно",
                "упорядоченном режиме",
                "обычном порядке",
                "обычном режиме",
                "без перемешивания",
                "не перемешивай",
            )
        ):
            shuffle = False

        # --------------------------------------------------------------
        # DEFAULT
        # --------------------------------------------------------------

        elif not mode:
            shuffle = None

        else:
            # Фраза похожа на команду, но режим неизвестен.
            # Не запускаем Spotify с догадкой.
            return None

        return Route(
            command="spotify_my_music",
            arguments={
                "shuffle": shuffle,
            },
        )


    # ------------------------------------------------------------------
    # CLOSE APPLICATION
    # ------------------------------------------------------------------

    def _route_close_application(
        self,
        text: str,
    ) -> Route | None:

        match = re.fullmatch(
            r"(?:"
            r"закрой|"
            r"закрыть|"
            r"выключи|"
            r"выключить"
            r")"
            r"(?:\s+приложение)?"
            r"\s+(.+)",
            text,
        )

        if not match:
            return None

        app_name = match.group(1).strip()

        if not app_name:
            return None

        return Route(
            command="close_application",
            arguments={
                "app_name": app_name,
            },
        )
