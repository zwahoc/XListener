"""Small Windows tray controller for the background XListener tasks."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from .config import Settings


TASK_NAME = "XListener Supervisor"
TRAY_TASK_NAME = "XListener Tray"


def _hidden_run(command: list[str]) -> None:
    subprocess.run(
        command,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _icon_image() -> Image.Image:
    image = Image.new("RGB", (64, 64), (24, 86, 160))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(24, 86, 160), outline=(220, 240, 255), width=2)
    draw.line((17, 17, 47, 47), fill="white", width=7)
    draw.line((47, 17, 17, 47), fill="white", width=7)
    return image


class TrayController:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._stopped = threading.Event()
        self.icon = pystray.Icon("XListener", _icon_image(), "XListener")
        self.icon.menu = pystray.Menu(
            pystray.MenuItem(self._status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause monitoring", self.pause),
            pystray.MenuItem("Resume monitoring", self.resume),
            pystray.MenuItem("Start supervisor", self.start_supervisor),
            pystray.MenuItem("Stop supervisor", self.stop_supervisor),
            pystray.MenuItem("Open listener log", self.open_listener_log),
            pystray.MenuItem("Open supervisor log", self.open_supervisor_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit tray (monitoring continues)", self.exit),
        )
        self._refresh_timer = threading.Thread(target=self._refresh_loop, daemon=True)

    def _status_text(self, _item=None) -> str:
        try:
            payload = json.loads(self.settings.runtime.supervisor_status_path.read_text(encoding="utf-8"))
            games = payload.get("game_running") or []
            if games:
                return "Paused: " + ", ".join(games)
            if payload.get("paused"):
                return "Paused manually"
            return "Running" if payload.get("daemon_running") else "Supervisor stopped"
        except (OSError, json.JSONDecodeError, TypeError):
            return "Status unavailable"

    def pause(self, _icon, _item) -> None:
        self.settings.runtime.pause_request_path.touch()

    def resume(self, _icon, _item) -> None:
        self.settings.runtime.pause_request_path.unlink(missing_ok=True)
        self.start_supervisor(_icon, _item)

    def start_supervisor(self, _icon=None, _item=None) -> None:
        self.settings.runtime.shutdown_request_path.unlink(missing_ok=True)
        _hidden_run(["schtasks.exe", "/Run", "/TN", TASK_NAME])

    def stop_supervisor(self, _icon=None, _item=None) -> None:
        self.settings.runtime.shutdown_request_path.touch()

    def open_listener_log(self, _icon, _item) -> None:
        os.startfile(self.settings.runtime.log_path)

    def open_supervisor_log(self, _icon, _item) -> None:
        os.startfile(self.settings.runtime.supervisor_log_path)

    def _refresh_loop(self) -> None:
        while not self._stopped.is_set():
            self.icon.update_menu()
            self._stopped.wait(3)

    def exit(self, _icon, _item) -> None:
        self._stopped.set()
        self.icon.stop()

    def run(self) -> None:
        self._refresh_timer.start()
        self.icon.run()


def run_tray(settings: Settings) -> None:
    TrayController(settings).run()
