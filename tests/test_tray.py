import json

from xlistener.config import load_settings
from xlistener.tray import TrayController


def make_controller(tmp_path) -> TrayController:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.pause_request_path = tmp_path / "pause.request"
    settings.runtime.shutdown_request_path = tmp_path / "shutdown.request"
    settings.runtime.supervisor_status_path = tmp_path / "supervisor-status.json"
    return TrayController(settings)


def test_tray_status_text_reflects_supervisor_state(tmp_path) -> None:
    controller = make_controller(tmp_path)
    controller.settings.runtime.supervisor_status_path.write_text(
        json.dumps({"daemon_running": True, "game_running": [], "paused": False}),
        encoding="utf-8",
    )

    assert controller._status_text() == "Running"


def test_tray_pause_and_resume_manage_request_marker(tmp_path, monkeypatch) -> None:
    controller = make_controller(tmp_path)
    started = []
    monkeypatch.setattr(controller, "start_supervisor", lambda *_args: started.append(True))

    controller.pause(None, None)
    assert controller.settings.runtime.pause_request_path.exists()

    controller.resume(None, None)
    assert not controller.settings.runtime.pause_request_path.exists()
    assert started == [True]
