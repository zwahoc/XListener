"""Configuration loading with safe local defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = Path(os.environ.get("LOCALAPPDATA", PROJECT_ROOT / "runtime")) / "XListener"


DEFAULT_INTERESTS = [
    {
        "topic": "Codex resets, limits, and usage changes",
        "priority": "high",
        "description": "Codex reset behavior, usage limits, quotas, reset timing, and allowance changes.",
    },
    {
        "topic": "Codex updates and releases",
        "priority": "high",
        "description": "New Codex releases, product updates, availability changes, fixes, and breaking changes.",
    },
    {
        "topic": "Codex and ChatGPT capabilities",
        "priority": "high",
        "description": "Meaningful Codex or ChatGPT capabilities, coding-agent behavior, tooling, integrations, and workflows.",
    },
]

DEFAULT_IGNORE = [
    "Memes, jokes, and humorous posts without substantive product information",
    "Generic marketing or promotional posts",
    "Generic questions asking users for opinions or feedback",
    "Routine conversational replies and social commentary",
    "Reposts with no meaningful new information",
    "General company news unrelated to Codex or a meaningful capability change",
]


def _runtime_path(value: str | Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    return Path(expanded)


class AccountConfig(BaseModel):
    handle: str = "thsottiaux"
    profile_url: str | None = None

    @field_validator("handle")
    @classmethod
    def normalize_handle(cls, value: str) -> str:
        return value.strip().lstrip("@").lower()

    def model_post_init(self, __context: Any) -> None:
        if not self.profile_url:
            self.profile_url = f"https://x.com/{self.handle}"


class FetcherConfig(BaseModel):
    type: str = "playwright_x"
    browser_channel: str = "chrome"
    poll_min_seconds: int = Field(default=10, ge=5)
    poll_max_seconds: int = Field(default=90, ge=5)
    max_posts_per_poll: int = Field(default=20, ge=1, le=100)
    bootstrap_mode: str = "baseline"
    include_replies: bool = True
    include_reposts: bool = True
    headless: bool = True
    storage_state_path: Path = DEFAULT_RUNTIME_DIR / "secrets" / "x_storage.json"
    browser_profile_path: Path = DEFAULT_RUNTIME_DIR / "browser" / "chrome-profile"

    @model_validator(mode="after")
    def validate_poll_range(self) -> "FetcherConfig":
        if self.poll_max_seconds < self.poll_min_seconds:
            raise ValueError("poll_max_seconds must be greater than or equal to poll_min_seconds")
        return self


class LlmConfig(BaseModel):
    model: str = "qwen3:4b"
    vision_model: str = "qwen3-vl:4b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0
    keep_alive: str = "10m"


class NotificationConfig(BaseModel):
    min_importance: int = Field(default=6, ge=1, le=10)
    chat_id_env: str = "TELEGRAM_CHAT_ID"
    parse_mode: str = "HTML"
    feedback_enabled: bool = True
    telegram_update_poll_seconds: int = Field(default=2, ge=1)


class LearningConfig(BaseModel):
    enabled: bool = True
    positive_rating_min: int = Field(default=6, ge=1, le=10)
    processed_id_retention_days: int = Field(default=30, ge=1)
    processed_id_max_rows: int = Field(default=2000, ge=100)
    max_examples_in_prompt: int = Field(default=6, ge=0, le=20)


class RuntimeConfig(BaseModel):
    database_path: Path = DEFAULT_RUNTIME_DIR / "xlistener.sqlite3"
    log_level: str = "INFO"
    dry_run: bool = False


class Settings(BaseModel):
    project_root: Path = PROJECT_ROOT
    account: AccountConfig = Field(default_factory=AccountConfig)
    fetcher: FetcherConfig = Field(default_factory=FetcherConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    interests: list[dict[str, Any]] = Field(default_factory=lambda: list(DEFAULT_INTERESTS))
    ignore: list[str] = Field(default_factory=lambda: list(DEFAULT_IGNORE))
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    def ensure_runtime_dirs(self) -> None:
        self.runtime.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.fetcher.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.fetcher.browser_profile_path.mkdir(parents=True, exist_ok=True)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Configuration root must be a mapping: {path}")
    return value


def load_settings(
    config_path: str | Path | None = None,
    preferences_path: str | Path | None = None,
) -> Settings:
    """Load YAML configuration and `.env` without exposing secret values."""

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    config_file = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
    raw = _read_yaml(config_file)

    monitored_handle = os.getenv("X_MONITORED_HANDLE", "").strip()
    if monitored_handle:
        account_raw = raw.setdefault("account", {})
        if not isinstance(account_raw, dict):
            raise ValueError("The account configuration must be a mapping")
        normalized_handle = monitored_handle.lstrip("@").lower()
        account_raw["handle"] = normalized_handle
        account_raw["profile_url"] = f"https://x.com/{normalized_handle}"

    if preferences_path:
        preference_raw = _read_yaml(Path(preferences_path))
        raw["interests"] = preference_raw.get("interests", raw.get("interests", DEFAULT_INTERESTS))
        raw["ignore"] = preference_raw.get("ignore", raw.get("ignore", DEFAULT_IGNORE))

    settings = Settings.model_validate(raw)
    settings.fetcher.storage_state_path = _runtime_path(settings.fetcher.storage_state_path)
    settings.fetcher.browser_profile_path = _runtime_path(settings.fetcher.browser_profile_path)
    settings.runtime.database_path = _runtime_path(settings.runtime.database_path)
    settings.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    settings.telegram_chat_id = os.getenv(settings.notification.chat_id_env)
    settings.ensure_runtime_dirs()
    return settings
