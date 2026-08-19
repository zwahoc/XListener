"""Windows-friendly lifecycle supervisor for gaming-aware XListener operation."""

from __future__ import annotations

import csv
import io
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import httpx

from .config import Settings
from .daemon import InstanceLock


LOG = logging.getLogger(__name__)


class ManagedProcess(Protocol):
    def poll(self) -> int | None: ...
    def wait(self, timeout: float | None = None) -> int: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...


ProcessFactory = Callable[[list[str], Path], ManagedProcess]
Sleep = Callable[[float], None]


def _tasklist_runner() -> str:
    completed = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.stdout


def running_process_names(runner: Callable[[], str] = _tasklist_runner) -> set[str]:
    """Return executable names visible to Windows tasklist."""

    names: set[str] = set()
    try:
        rows = csv.reader(io.StringIO(runner()))
        for row in rows:
            if row and row[0] and not row[0].startswith("INFO:"):
                names.add(row[0].strip().lower())
    except (csv.Error, OSError):
        return names
    return names


def game_processes_running(
    configured_processes: list[str],
    runner: Callable[[], str] = _tasklist_runner,
) -> list[str]:
    active = running_process_names(runner)
    return [name for name in configured_processes if name.strip().lower() in active]


def unload_ollama_models(settings: Settings) -> list[str]:
    """Ask Ollama to unload XListener's models from memory."""

    unloaded: list[str] = []
    models = [settings.llm.model]
    if settings.llm.vision_model not in models:
        models.append(settings.llm.vision_model)
    endpoint = settings.llm.base_url.rstrip("/") + "/api/generate"
    for model in models:
        try:
            response = httpx.post(endpoint, json={"model": model, "keep_alive": 0}, timeout=10)
            response.raise_for_status()
            unloaded.append(model)
            LOG.info("Requested Ollama unload for %s", model)
        except Exception as exc:
            LOG.warning("Could not unload Ollama model %s: %s", model, exc)
    return unloaded


def _default_process_factory(command: list[str], cwd: Path) -> ManagedProcess:
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


@dataclass(frozen=True)
class SupervisorStatus:
    daemon_running: bool
    game_running: tuple[str, ...]
    daemon_pid: int | None


class GamingSupervisor:
    def __init__(
        self,
        settings: Settings,
        process_factory: ProcessFactory = _default_process_factory,
        process_runner: Callable[[], str] = _tasklist_runner,
        unload_models: Callable[[Settings], list[str]] = unload_ollama_models,
        sleep: Sleep | None = None,
    ):
        self.settings = settings
        self.process_factory = process_factory
        self.process_runner = process_runner
        self.unload_models = unload_models
        self.sleep = sleep or __import__("time").sleep
        self.process: ManagedProcess | None = None
        self._paused = False

    def _write_status(self, games: list[str], paused: bool) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "daemon_running": self.process is not None and self.process.poll() is None,
            "daemon_pid": getattr(self.process, "pid", None),
            "game_running": games,
            "paused": paused,
        }
        path = self.settings.runtime.supervisor_status_path
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            LOG.warning("Could not write supervisor status: %s", exc)

    @property
    def command(self) -> list[str]:
        return [sys.executable, "-m", "xlistener", "run"]

    def games_running(self) -> list[str]:
        if not self.settings.gaming.enabled:
            return []
        return game_processes_running(self.settings.gaming.processes, self.process_runner)

    def status(self) -> SupervisorStatus:
        games = tuple(self.games_running())
        running = self.process is not None and self.process.poll() is None
        return SupervisorStatus(
            daemon_running=running,
            game_running=games,
            daemon_pid=getattr(self.process, "pid", None) if running else None,
        )

    def start_daemon(self) -> bool:
        if self.process is not None and self.process.poll() is None:
            return False
        self.settings.runtime.stop_request_path.unlink(missing_ok=True)
        self.process = self.process_factory(self.command, self.settings.project_root)
        LOG.info("Started XListener daemon (pid=%s)", getattr(self.process, "pid", "unknown"))
        return True

    def stop_daemon(self) -> bool:
        if self.process is None or self.process.poll() is not None:
            self.process = None
            return False
        self.settings.runtime.stop_request_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings.runtime.stop_request_path.touch()
        try:
            self.process.wait(timeout=self.settings.gaming.stop_grace_seconds)
            LOG.info("XListener daemon stopped cooperatively")
        except subprocess.TimeoutExpired:
            LOG.warning("Daemon did not stop within grace period; terminating it")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                LOG.error("Daemon did not terminate; killing it")
                self.process.kill()
                self.process.wait(timeout=5)
        finally:
            self.settings.runtime.stop_request_path.unlink(missing_ok=True)
            self.process = None
        if self.settings.gaming.unload_ollama_models:
            self.unload_models(self.settings)
        return True

    def cycle_once(self) -> SupervisorStatus:
        games = self.games_running()
        if games:
            if self.stop_daemon():
                LOG.info("Paused XListener for game process(es): %s", ", ".join(games))
        elif self.process is None or self.process.poll() is not None:
            self.start_daemon()
        return self.status()

    def run_forever(self) -> None:
        with InstanceLock(self.settings.runtime.supervisor_lock_path):
            was_paused = False
            try:
                while True:
                    if self.settings.runtime.shutdown_request_path.exists():
                        LOG.info("Shutdown requested by tray controller")
                        break
                    games = self.games_running()
                    manually_paused = self.settings.runtime.pause_request_path.exists()
                    paused = bool(games) or manually_paused
                    if paused:
                        if games and not was_paused:
                            LOG.info("Gaming detected: %s", ", ".join(games))
                        elif manually_paused and not was_paused:
                            LOG.info("Manual pause requested")
                        self.stop_daemon()
                        was_paused = True
                    else:
                        if was_paused:
                            LOG.info("Gaming ended; waiting %s seconds before restart", self.settings.gaming.restart_delay_seconds)
                            self.sleep(self.settings.gaming.restart_delay_seconds)
                        if self.process is None or self.process.poll() is not None:
                            self.start_daemon()
                        was_paused = False
                    self._write_status(games, paused)
                    self.sleep(self.settings.gaming.check_interval_seconds)
            finally:
                self.stop_daemon()
                self._write_status([], False)
