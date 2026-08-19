from pathlib import Path

from xlistener.config import load_settings


def test_defaults_target_thsottiaux(tmp_path: Path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")

    assert settings.account.handle == "thsottiaux"
    assert settings.account.profile_url == "https://x.com/thsottiaux"
    assert settings.fetcher.headless is True
    assert settings.fetcher.browser_channel == "chrome"
    assert settings.fetcher.poll_min_seconds == 10
    assert settings.fetcher.poll_max_seconds == 90
    assert settings.llm.model == "qwen3:4b"
    assert settings.author_context["products_of_interest"] == ["Codex", "ChatGPT", "ChatGPT Work", "Codex-CLI"]
    assert len(settings.entity_context) == 11
    assert settings.entity_context[0]["products"] == ["Claude", "Claude Code", "Opus 5", "Fable 5"]
    assert settings.entity_context[-1]["organization"] == "Microsoft"


def test_environment_handle_overrides_yaml_account(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "account:\n  handle: yaml_account\n  profile_url: https://x.com/yaml_account\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("X_MONITORED_HANDLE", "@env_account")

    settings = load_settings(config_path=config_path)

    assert settings.account.handle == "env_account"
    assert settings.account.profile_url == "https://x.com/env_account"
    assert settings.author_context["handle"] == "env_account"
    assert settings.author_context["name"] == "unknown"
