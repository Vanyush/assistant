from __future__ import annotations

import configparser
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass(slots=True)
class Application:
    name: str
    generic_name: str
    desktop_file: Path | None
    exec_command: str | None
    flatpak_id: str | None


class ApplicationResolver:
    """
    Универсальный resolver Linux-приложений.

    Поддерживает:
        - обычные .desktop-приложения;
        - Flatpak-приложения;
        - русские aliases;
        - запуск;
        - завершение процессов.
    """

    APPLICATION_DIRS = (
        Path.home() / ".local/share/applications",
        Path("/usr/share/applications"),
    )

    ALIASES = {
        # Spotify
        "spotify": "spotify",
        "спотифай": "spotify",

        # Telegram
        "telegram": "telegram",
        "телеграм": "telegram",
        "телега": "telegram",
        "телеграмм": "telegram",

        # Chrome
        "chrome": "chrome",
        "хром": "chrome",
        "гугл хром": "chrome",

        # Firefox
        "firefox": "firefox",
        "фаерфокс": "firefox",
        "файрфокс": "firefox",

        # Browser
        "браузер": "browser",

        # Text editor
        "marktext": "marktext",\n        "марк текст": "marktext",\n        "блокнот": "text editor",
        "текстовый редактор": "text editor",
        "редактор": "text editor",

        # File manager
        "файлы": "file manager",
        "проводник": "file manager",
        "файловый менеджер": "file manager",

        # Heroic
        "heroic": "heroic",
        "херойк": "heroic",

        # OBS
        "obs": "obs",
        "обс": "obs",

        # ONLYOFFICE
        "onlyoffice": "onlyoffice",
        "онли офис": "onlyoffice",
        "офис": "onlyoffice",

        # Prism Launcher
        "prism": "prism launcher",
        "prism launcher": "prism launcher",
        "призм": "prism launcher",
        "майнкрафт": "prism launcher"
    }

    FLATPAK_APPS = {
        "spotify": "com.spotify.Client",
        "telegram": "org.telegram.desktop",
        "heroic": "com.heroicgameslauncher.hgl",
        "obs": "com.obsproject.Studio",
        "onlyoffice": "org.onlyoffice.desktopeditors",
        "prism launcher": "org.prismlauncher.PrismLauncher",
    }

    PREFERRED_DESKTOP_NAMES = {
        "spotify": {
            "spotify",
        },

        "chrome": {
            "google chrome",
        },

        "firefox": {
            "firefox web browser",
            "firefox",
        },

        "text editor": {
            "text editor",
        },

        "file manager": {
            "files",
        },
    }

    CATEGORY_KEYWORDS = {
        "browser": {
            "firefox web browser",
        },

        "text editor": {
            "text editor",
        },

        "file manager": {
            "files",
        },
    }

    def __init__(self) -> None:
        self.applications = self._load_desktop_applications()
        self.flatpak_ids = self._load_flatpak_applications()

    # ==================================================================
    # NORMALIZATION
    # ==================================================================

    @staticmethod
    def normalize(text: str) -> str:
        text = text.lower().strip()

        text = text.replace("ё", "е")

        text = re.sub(
            r"[^\w\s-]",
            " ",
            text,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ==================================================================
    # DESKTOP FILES
    # ==================================================================

    def _load_desktop_applications(self) -> list[Application]:
        applications: list[Application] = []

        for directory in self.APPLICATION_DIRS:
            if not directory.exists():
                continue

            for desktop_file in directory.glob("*.desktop"):
                app = self._parse_desktop_file(
                    desktop_file
                )

                if app is not None:
                    applications.append(app)

        return applications

    def _parse_desktop_file(
        self,
        desktop_file: Path,
    ) -> Application | None:

        parser = configparser.ConfigParser(
            interpolation=None,
            strict=False,
        )

        try:
            parser.read(
                desktop_file,
                encoding="utf-8",
            )
        except (
            OSError,
            UnicodeDecodeError,
            configparser.Error,
        ):
            return None

        if not parser.has_section("Desktop Entry"):
            return None

        entry = parser["Desktop Entry"]

        if entry.get("Type", "") != "Application":
            return None

        if entry.get("Hidden", "").lower() == "true":
            return None

        if entry.get("NoDisplay", "").lower() == "true":
            return None

        name = entry.get(
            "Name",
            "",
        ).strip()

        generic_name = entry.get(
            "GenericName",
            "",
        ).strip()

        exec_command = entry.get(
            "Exec",
            "",
        ).strip()

        if not name:
            return None

        return Application(
            name=name,
            generic_name=generic_name,
            desktop_file=desktop_file,
            exec_command=exec_command or None,
            flatpak_id=None,
        )

    # ==================================================================
    # FLATPAK
    # ==================================================================

    def _load_flatpak_applications(self) -> set[str]:
        if shutil.which("flatpak") is None:
            return set()

        try:
            result = subprocess.run(
                [
                    "flatpak",
                    "list",
                    "--app",
                    "--columns=application",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

        except (
            OSError,
            subprocess.CalledProcessError,
        ):
            return set()

        return {
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        }

    def _flatpak_installed(
        self,
        app_id: str,
    ) -> bool:
        return app_id in self.flatpak_ids

    # ==================================================================
    # ALIASES
    # ==================================================================

    def _resolve_alias(
        self,
        query: str,
    ) -> str:

        normalized = self.normalize(query)

        return self.ALIASES.get(
            normalized,
            normalized,
        )

    # ==================================================================
    # RESOLVE
    # ==================================================================

    def resolve(
        self,
        query: str,
    ) -> Application | None:

        canonical = self._resolve_alias(query)

        # --------------------------------------------------------------
        # 1. Flatpak — приоритет для явно известных Flatpak apps
        # --------------------------------------------------------------

        flatpak_id = self.FLATPAK_APPS.get(
            canonical
        )

        if (
            flatpak_id is not None
            and self._flatpak_installed(flatpak_id)
        ):
            display_names = {
                "spotify": "Spotify",
                "telegram": "Telegram",
                "heroic": "Heroic Games Launcher",
                "obs": "OBS Studio",
                "onlyoffice": "ONLYOFFICE",
                "prism launcher": "Prism Launcher",
            }

            return Application(
                name=display_names.get(
                    canonical,
                    canonical,
                ),
                generic_name="",
                desktop_file=None,
                exec_command=None,
                flatpak_id=flatpak_id,
            )

        # --------------------------------------------------------------
        # 2. Предпочтительное desktop имя
        # --------------------------------------------------------------

        preferred_names = (
            self.PREFERRED_DESKTOP_NAMES.get(
                canonical,
                set(),
            )
        )

        for app in self.applications:
            app_name = self.normalize(
                app.name
            )

            if app_name in preferred_names:
                return app

        # --------------------------------------------------------------
        # 3. Категория
        # --------------------------------------------------------------

        keywords = self.CATEGORY_KEYWORDS.get(
            canonical,
            set(),
        )

        if keywords:
            for app in self.applications:
                name = self.normalize(
                    app.name
                )

                generic_name = self.normalize(
                    app.generic_name
                )

                combined = (
                    f"{name} {generic_name}"
                )

                for keyword in keywords:
                    if keyword in combined:
                        return app

        # --------------------------------------------------------------
        # 4. Точное имя
        # --------------------------------------------------------------

        for app in self.applications:
            name = self.normalize(
                app.name
            )

            if name == canonical:
                return app

        # --------------------------------------------------------------
        # 5. GenericName
        # --------------------------------------------------------------

        for app in self.applications:
            generic_name = self.normalize(
                app.generic_name
            )

            if (
                generic_name
                and generic_name == canonical
            ):
                return app

        # --------------------------------------------------------------
        # 6. Частичное совпадение
        # --------------------------------------------------------------

        for app in self.applications:
            name = self.normalize(
                app.name
            )

            if canonical in name:
                return app

        # --------------------------------------------------------------
        # 7. Desktop filename
        # --------------------------------------------------------------

        for app in self.applications:
            if app.desktop_file is None:
                continue

            filename = self.normalize(
                app.desktop_file.stem
            )

            if canonical in filename:
                return app

        return None

    # ==================================================================
    # LAUNCH
    # ==================================================================

    def launch(
        self,
        query: str,
    ) -> str:

        canonical = self._resolve_alias(query)

        app = self.resolve(query)

        if app is None:
            return (
                f"Не удалось найти приложение "
                f"'{query}' в системе."
            )

        # --------------------------------------------------------------
        # Flatpak
        # --------------------------------------------------------------

        if app.flatpak_id is not None:

            try:
                subprocess.Popen(
                    [
                        "flatpak",
                        "run",
                        app.flatpak_id,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

            except OSError as exc:
                return (
                    f"Ошибка запуска "
                    f"{app.name}: {exc}"
                )

            return (
                f"Приложение "
                f"{app.name} успешно запущено."
            )

        # --------------------------------------------------------------
        # Desktop application
        # --------------------------------------------------------------

        if app.desktop_file is None:
            return (
                f"Для приложения "
                f"{app.name} не найден launcher."
            )

        if shutil.which("gio") is None:
            return (
                "В системе отсутствует команда gio."
            )

        try:
            subprocess.Popen(
                [
                    "gio",
                    "launch",
                    str(app.desktop_file),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        except OSError as exc:
            return (
                f"Ошибка запуска "
                f"{app.name}: {exc}"
            )

        return (
            f"Приложение "
            f"{app.name} успешно запущено."
        )

    # ==================================================================
    # CLOSE
    # ==================================================================

    def close(
        self,
        query: str,
    ) -> str:

        app = self.resolve(query)

        if app is None:
            return (
                f"Не удалось найти приложение "
                f"'{query}' в системе."
            )

        process_names = {
            name.lower()
            for name in self._get_process_names(app)
        }

        if not process_names:
            return (
                f"Не удалось определить процесс "
                f"приложения {app.name}."
            )

        targets: list[psutil.Process] = []

        # --------------------------------------------------------------
        # Find matching processes
        # --------------------------------------------------------------

        for process in psutil.process_iter(
            ["pid", "ppid", "name", "cmdline"]
        ):
            try:
                name = (
                    process.info["name"]
                    or ""
                ).lower()

                cmdline = (
                    process.info["cmdline"]
                    or []
                )

                command_line = " ".join(
                    cmdline
                ).lower()

                matched = (
                    name in process_names
                    or any(
                        candidate in command_line
                        for candidate in process_names
                    )
                )

                if matched:
                    targets.append(process)

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        if not targets:
            return (
                f"Приложение {app.name} "
                f"сейчас не запущено."
            )

        # --------------------------------------------------------------
        # Prefer top-level processes
        # --------------------------------------------------------------

        roots: list[psutil.Process] = []

        target_pids = {
            process.pid
            for process in targets
        }

        for process in targets:
            try:
                parent = process.parent()

                if (
                    parent is None
                    or parent.pid not in target_pids
                ):
                    roots.append(process)

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
            ):
                continue

        # --------------------------------------------------------------
        # Terminate process trees
        # --------------------------------------------------------------

        all_processes: list[psutil.Process] = []

        for root in roots:
            try:
                children = root.children(
                    recursive=True
                )

                all_processes.extend(children)
                all_processes.append(root)

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
            ):
                continue

        # Убираем дубликаты.
        unique_processes = {
            process.pid: process
            for process in all_processes
        }

        processes = list(
            unique_processes.values()
        )

        # --------------------------------------------------------------
        # SIGTERM
        # --------------------------------------------------------------

        for process in processes:
            try:
                process.terminate()

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
            ):
                pass

        gone, alive = psutil.wait_procs(
            processes,
            timeout=3.0,
        )

        # --------------------------------------------------------------
        # SIGKILL, только если процесс не завершился
        # --------------------------------------------------------------

        for process in alive:
            try:
                process.kill()

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
            ):
                pass

        if gone or alive:
            return (
                f"Приложение {app.name} "
                f"закрыто."
            )

        return (
            f"Не удалось закрыть "
            f"{app.name}."
        )

    # ==================================================================
    # PROCESS DETECTION
    # ==================================================================

    def _get_process_names(
        self,
        app: Application,
    ) -> list[str]:

        # --------------------------------------------------------------
        # Flatpak applications
        # --------------------------------------------------------------

        flatpak_processes = {
            "org.telegram.desktop": [
                "Telegram",
                "telegram",
            ],

            "com.spotify.Client": [
                "spotify",
            ],

            "com.obsproject.Studio": [
                "obs",
                "obs-studio",
            ],

            "com.heroicgameslauncher.hgl": [
                "heroic",
                "heroicgameslauncher",
            ],

            "org.onlyoffice.desktopeditors": [
                "desktopeditors",
            ],

            "org.prismlauncher.PrismLauncher": [
                "prismlauncher",
            ],
        }

        if app.flatpak_id in flatpak_processes:
            return flatpak_processes[
                app.flatpak_id
            ]

        # --------------------------------------------------------------
        # Known native applications
        # --------------------------------------------------------------

        native_processes = {
            "Google Chrome": [
                "chrome",
                "google-chrome",
                "google-chrome-stable",
            ],

            "Firefox Web Browser": [
                "firefox",
            ],

            "Firefox": [
                "firefox",
            ],

            "Text Editor": [
                "xed",
            ],

            "Files": [
                "nemo",
            ],

            "Spotify": [
                "spotify",
            ],

            "Telegram": [
                "Telegram",
                "telegram",
            ],
        }

        if app.name in native_processes:
            return native_processes[
                app.name
            ]

        # --------------------------------------------------------------
        # Fallback: derive executable from .desktop Exec
        # --------------------------------------------------------------

        if app.exec_command:
            command = re.sub(
                r"%[uUfFiIcCk]",
                "",
                app.exec_command,
            ).strip()

            if command:
                executable = command.split()[0]

                executable = Path(
                    executable
                ).name

                if executable:
                    return [executable]

        return []

    # ==================================================================
    # DEBUG
    # ==================================================================

    def search(
        self,
        query: str,
    ) -> list[Application]:

        canonical = self._resolve_alias(query)

        result: list[Application] = []

        for app in self.applications:

            name = self.normalize(
                app.name
            )

            generic_name = self.normalize(
                app.generic_name
            )

            if (
                canonical in name
                or canonical in generic_name
            ):
                result.append(app)

        flatpak_id = self.FLATPAK_APPS.get(
            canonical
        )

        if (
            flatpak_id is not None
            and self._flatpak_installed(flatpak_id)
        ):
            result.append(
                Application(
                    name=canonical,
                    generic_name="",
                    desktop_file=None,
                    exec_command=None,
                    flatpak_id=flatpak_id,
                )
            )

        return result
