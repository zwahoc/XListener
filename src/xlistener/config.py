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

DEFAULT_AUTHOR_CONTEXT = {
    "handle": "thsottiaux",
    "name": "Tibo",
    "organization": "OpenAI",
    "role": "OpenAI employee",
    "products_of_interest": ["Codex", "ChatGPT", "ChatGPT Work", "Codex-CLI"],
    "notes": [
        "The account may post product information, competitive commentary, jokes, sarcasm, marketing, and engagement questions.",
        "Do not treat every post as an official announcement or literal statement.",
    ],
}

DEFAULT_ENTITY_CONTEXT = [
    {
        "organization": "Anthropic",
        "relationship": "direct competitor",
        "handles": ["claudedevs", "claudeai", "anthropicai"],
        "products": ["Claude", "Claude Code", "Opus 5", "Fable 5"],
        "description": "Strongest overlap with OpenAI in frontier models, coding agents, APIs, and enterprise AI.",
    },
    {
        "organization": "Google DeepMind",
        "relationship": "direct competitor",
        "handles": ["googledeepmind", "geminiapp", "googleai"],
        "products": ["Gemini", "Gemini 3.5", "Gemini 3.6 Flash", "Gemini API"],
        "description": "Competes across general AI, multimodal models, coding, agents, and enterprise AI.",
    },
    {
        "organization": "xAI",
        "relationship": "direct competitor",
        "handles": ["xai", "grok"],
        "products": ["Grok", "Grok 4.6", "Grok API", "Grok Build"],
        "description": "Competes with ChatGPT, OpenAI models, APIs, and coding or agent products.",
    },
    {
        "organization": "Moonshot AI",
        "relationship": "competitor",
        "handles": ["moonshot_ai", "kimi_moonshot"],
        "products": ["Kimi", "Kimi K3", "Kimi Code", "Kimi Work"],
        "description": "Competes in reasoning, coding, long-context models, and agents.",
    },
    {
        "organization": "Alibaba / Qwen",
        "relationship": "competitor",
        "handles": ["qwen", "alibaba_cloud"],
        "products": ["Qwen", "Qwen3.8-Max", "Qwen Code", "Qwen3-Coder"],
        "description": "Strong competitor in open models, coding, APIs, and agentic AI.",
    },
    {
        "organization": "Meta",
        "relationship": "competitor",
        "handles": ["metaai", "aiatmeta"],
        "products": ["Meta AI", "Llama", "Muse"],
        "description": "Competes in assistants, foundation models, multimodal AI, and open models.",
    },
    {
        "organization": "DeepSeek",
        "relationship": "competitor",
        "handles": ["deepseek_ai"],
        "products": ["DeepSeek", "DeepSeek V4 Pro", "DeepSeek API"],
        "description": "Competes heavily on reasoning, coding, and price-to-performance.",
    },
    {
        "organization": "Z.ai / Zhipu AI",
        "relationship": "competitor",
        "handles": ["zhipuai", "chatglm"],
        "products": ["GLM", "GLM-5.3", "ZCode"],
        "description": "Competes in foundation models, coding agents, and enterprise AI.",
    },
    {
        "organization": "MiniMax",
        "relationship": "competitor",
        "handles": ["minimax_ai"],
        "products": ["MiniMax M3", "MiniMax H3", "MiniMax API"],
        "description": "Competes across LLMs, coding, agents, image, video, and audio AI.",
    },
    {
        "organization": "Mistral AI",
        "relationship": "competitor",
        "handles": ["mistralai"],
        "products": ["Le Chat", "Mistral Large", "Devstral", "Mistral Vibe"],
        "description": "Competes in enterprise AI, APIs, open models, and coding.",
    },
    {
        "organization": "Microsoft",
        "relationship": "strategic partner, investor, and partial competitor",
        "handles": ["microsoft", "msft", "github"],
        "products": ["Microsoft Copilot", "GitHub Copilot", "Azure OpenAI", "Microsoft Foundry"],
        "description": "Closely partnered with OpenAI, but also builds overlapping AI products and platforms.",
    },
]

DEFAULT_INTERPRETATION_RULES = [
    "Evaluate the monitored author's own text as the primary evidence.",
    "Use parent, quoted, and reposted posts to identify the subject, organization, products, and claims being discussed, not to transfer their importance automatically.",
    "A short reply must add concrete information to receive a high importance score.",
    "A reply that only jokes, reacts, agrees, mocks, or makes an ambiguous remark should usually score low.",
    "If tone or meaning is uncertain, be conservative and say so in the reasoning.",
    "Competitor-only news is not automatically relevant to Codex or ChatGPT, but a monitored reply can still be relevant as competitive commentary or strategic positioning even when it does not mention Codex.",
    "When a short monitored reply depends on its parent, summarize the parent subject and then clearly separate the monitored author's words, inferred stance, and the parent's factual claims.",
    "Do not assume an unknown product belongs to OpenAI or that its changes affect Codex.",
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
    log_path: Path = DEFAULT_RUNTIME_DIR / "xlistener.log"
    supervisor_log_path: Path = DEFAULT_RUNTIME_DIR / "supervisor.log"
    instance_lock_path: Path = DEFAULT_RUNTIME_DIR / "xlistener.lock"
    supervisor_lock_path: Path = DEFAULT_RUNTIME_DIR / "supervisor.lock"
    stop_request_path: Path = DEFAULT_RUNTIME_DIR / "stop.request"
    pause_request_path: Path = DEFAULT_RUNTIME_DIR / "pause.request"
    shutdown_request_path: Path = DEFAULT_RUNTIME_DIR / "shutdown.request"
    supervisor_status_path: Path = DEFAULT_RUNTIME_DIR / "supervisor-status.json"
    log_level: str = "INFO"
    dry_run: bool = False
    retry_base_seconds: int = Field(default=30, ge=1)
    retry_max_seconds: int = Field(default=1800, ge=1)
    poll_error_seconds: int = Field(default=120, ge=5)
    auth_error_seconds: int = Field(default=900, ge=30)

    @model_validator(mode="after")
    def validate_retry_range(self) -> "RuntimeConfig":
        if self.retry_max_seconds < self.retry_base_seconds:
            raise ValueError("retry_max_seconds must be greater than or equal to retry_base_seconds")
        return self


class GamingConfig(BaseModel):
    enabled: bool = True
    processes: list[str] = Field(
        default_factory=lambda: [
            "VALORANT-Win64-Shipping.exe",
            "VALORANT.exe",
            "cs2.exe",
            "LoveChoice.exe",
        ]
    )
    check_interval_seconds: int = Field(default=3, ge=1)
    stop_grace_seconds: int = Field(default=10, ge=1)
    restart_delay_seconds: int = Field(default=30, ge=1)
    unload_ollama_models: bool = True


class Settings(BaseModel):
    project_root: Path = PROJECT_ROOT
    account: AccountConfig = Field(default_factory=AccountConfig)
    fetcher: FetcherConfig = Field(default_factory=FetcherConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    gaming: GamingConfig = Field(default_factory=GamingConfig)
    interests: list[dict[str, Any]] = Field(default_factory=lambda: list(DEFAULT_INTERESTS))
    ignore: list[str] = Field(default_factory=lambda: list(DEFAULT_IGNORE))
    author_context: dict[str, Any] = Field(default_factory=lambda: dict(DEFAULT_AUTHOR_CONTEXT))
    entity_context: list[dict[str, Any]] = Field(default_factory=lambda: list(DEFAULT_ENTITY_CONTEXT))
    interpretation_rules: list[str] = Field(default_factory=lambda: list(DEFAULT_INTERPRETATION_RULES))
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    @model_validator(mode="after")
    def align_author_context(self) -> "Settings":
        context_handle = str(self.author_context.get("handle", "")).strip().lstrip("@").lower()
        if context_handle and context_handle != self.account.handle:
            self.author_context = {
                "handle": self.account.handle,
                "name": "unknown",
                "organization": "unknown",
                "role": "unknown",
                "products_of_interest": [],
                "notes": ["No account-specific background has been configured for this monitored handle."],
            }
        return self

    def ensure_runtime_dirs(self) -> None:
        self.runtime.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.supervisor_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.instance_lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.supervisor_lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.stop_request_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.pause_request_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.shutdown_request_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.supervisor_status_path.parent.mkdir(parents=True, exist_ok=True)
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
        raw["author_context"] = preference_raw.get("author_context", raw.get("author_context", DEFAULT_AUTHOR_CONTEXT))
        raw["entity_context"] = preference_raw.get("entity_context", raw.get("entity_context", DEFAULT_ENTITY_CONTEXT))
        raw["interpretation_rules"] = preference_raw.get(
            "interpretation_rules", raw.get("interpretation_rules", DEFAULT_INTERPRETATION_RULES)
        )

    settings = Settings.model_validate(raw)
    settings.fetcher.storage_state_path = _runtime_path(settings.fetcher.storage_state_path)
    settings.fetcher.browser_profile_path = _runtime_path(settings.fetcher.browser_profile_path)
    settings.runtime.database_path = _runtime_path(settings.runtime.database_path)
    settings.runtime.log_path = _runtime_path(settings.runtime.log_path)
    settings.runtime.supervisor_log_path = _runtime_path(settings.runtime.supervisor_log_path)
    settings.runtime.instance_lock_path = _runtime_path(settings.runtime.instance_lock_path)
    settings.runtime.supervisor_lock_path = _runtime_path(settings.runtime.supervisor_lock_path)
    settings.runtime.stop_request_path = _runtime_path(settings.runtime.stop_request_path)
    settings.runtime.pause_request_path = _runtime_path(settings.runtime.pause_request_path)
    settings.runtime.shutdown_request_path = _runtime_path(settings.runtime.shutdown_request_path)
    settings.runtime.supervisor_status_path = _runtime_path(settings.runtime.supervisor_status_path)
    settings.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    settings.telegram_chat_id = os.getenv(settings.notification.chat_id_env)
    settings.ensure_runtime_dirs()
    return settings
