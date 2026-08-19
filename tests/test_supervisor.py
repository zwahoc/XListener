import json
import csv
import io

from xlistener.config import load_settings
from xlistener.supervisor import GamingSupervisor, game_processes_running, running_process_names


def tasklist_csv(*names: str) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    for name in names:
        writer.writerow([name, "1234", "Console", "1", "10 K"])
    return output.getvalue()


def test_process_detector_matches_configured_names_case_insensitively() -> None:
    output = tasklist_csv("VALORANT-Win64-Shipping.exe", "steam.exe")

    assert running_process_names(lambda: output) == {"valorant-win64-shipping.exe", "steam.exe"}
    assert game_processes_running(
        ["VALORANT-Win64-Shipping.exe", "cs2.exe"],
        lambda: output,
    ) == ["VALORANT-Win64-Shipping.exe"]


class FakeProcess:
    def __init__(self):
        self.pid = 123
        self.exit_code = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.exit_code

    def wait(self, timeout=None):
        self.exit_code = 0
        return self.exit_code

    def terminate(self):
        self.terminated = True
        self.exit_code = 1

    def kill(self):
        self.killed = True
        self.exit_code = 9


def test_supervisor_stops_for_game_and_unloads_models(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.stop_request_path = tmp_path / "stop.request"
    settings.runtime.supervisor_lock_path = tmp_path / "supervisor.lock"
    settings.gaming.processes = ["VALORANT-Win64-Shipping.exe"]
    process = FakeProcess()
    unloaded = []

    supervisor = GamingSupervisor(
        settings,
        process_factory=lambda command, cwd: process,
        process_runner=lambda: tasklist_csv("VALORANT-Win64-Shipping.exe"),
        unload_models=lambda value: unloaded.append(value.llm.model) or [value.llm.model],
    )
    supervisor.start_daemon()
    status = supervisor.cycle_once()

    assert status.daemon_running is False
    assert status.game_running == ("VALORANT-Win64-Shipping.exe",)
    assert process.terminated is False
    assert unloaded == [settings.llm.model]
    assert not settings.runtime.stop_request_path.exists()


def test_supervisor_starts_when_no_game_is_active(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.stop_request_path = tmp_path / "stop.request"
    settings.runtime.supervisor_lock_path = tmp_path / "supervisor.lock"
    process = FakeProcess()

    supervisor = GamingSupervisor(
        settings,
        process_factory=lambda command, cwd: process,
        process_runner=lambda: "",
        unload_models=lambda value: [],
    )

    status = supervisor.cycle_once()

    assert status.daemon_running is True
    assert status.game_running == ()
