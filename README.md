# XListener

**Local-first monitoring for one X account, with on-device relevance filtering and private Telegram notifications.**

XListener watches a configurable X account through a dedicated authenticated Chrome profile. It evaluates new posts with a local Ollama model, then delivers only the posts that meet your relevance threshold to a private Telegram chat. It is designed for personal, high-signal monitoring—not social analytics, bulk archiving, or multi-user operation.

> **Platform support:** Windows 11 is the only supported and intended deployment platform. This project has not been tested on macOS or Linux.

## Highlights

- Monitors authored posts, replies, reposts, and bounded related-post context.
- Runs text classification locally through Ollama; no hosted LLM is required.
- Produces structured relevance, importance, summary, reasoning, tone, stance, and tags.
- Sends compact Telegram notifications with a direct link to the original post.
- Learns bounded tag affinity from inline usefulness ratings (1–10).
- Lets you recover a missed post by submitting a single X status URL to Telegram.
- Preserves notification and retry state in SQLite while discarding ignored post content.
- Can run at Windows sign-in, pause for configured games, and be controlled from the system tray.

## How It Works

```text
X account → authenticated Chrome session → context resolution → local Ollama model
                                                             ↓
                                                     SQLite decision state
                                                             ↓
                                                    private Telegram chat
                                                             ↓
                                                       rating feedback
```

The first polling cycle uses a baseline cursor by default, so existing posts do not generate a flood of notifications. Later posts are processed oldest first. Qualifying posts are saved before Telegram delivery; retries reuse saved analysis rather than asking the model to classify the same post again.

## Requirements

- Windows 11
- Python 3.11–3.14
- Git and Google Chrome
- [Ollama](https://ollama.com/) with the configured model (`qwen3:8b` by default)
- A Telegram bot and a private chat ID
- An X account for the dedicated browser session

## Quick Start

```powershell
git clone https://github.com/zwahoc/XListener.git
Set-Location XListener
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
ollama pull qwen3:8b
Copy-Item .env.example .env
Copy-Item config/config.example.yaml config.yaml
Copy-Item config/preferences.example.yaml preferences.yaml
```

Add your Telegram values to `.env`, save the X credentials in Windows Credential Manager, and complete the browser sign-in:

```powershell
.\.venv\Scripts\python.exe scripts/store_x_credentials.py
.\.venv\Scripts\python.exe -m xlistener auth-x --manual
.\.venv\Scripts\python.exe -m xlistener check
```

When the checks are satisfactory, register the background supervisor and tray controller:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_xlistener_task.ps1
```

See the [installation guide](doc/getting-started/installation.md) for the complete setup, security notes, and troubleshooting guidance.

## Common Commands

```powershell
# Verify local prerequisites and configuration
.\.venv\Scripts\python.exe -m xlistener check

# Inspect local state and learned preferences
.\.venv\Scripts\python.exe -m xlistener db-status

# Fetch or run one diagnostic cycle
.\.venv\Scripts\python.exe -m xlistener fetch-once --limit 5
.\.venv\Scripts\python.exe -m xlistener run-once

# Preview the latest qualifying notification without sending it
.\.venv\Scripts\python.exe -m xlistener notify-latest --dry-run
```

For normal use, manage the service from the XListener tray icon. Do not start a standalone daemon while the supervisor is active.

## Documentation

Start with the [documentation index](doc/README.md). The most useful guides are:

- [Installation](doc/getting-started/installation.md)
- [Configuration](doc/getting-started/configuration.md)
- [Operations and troubleshooting](doc/getting-started/operations.md)
- [Architecture](doc/engineering/architecture.md)
- [Security and privacy](doc/engineering/security-and-privacy.md)

## Status and Scope

The text-monitoring pipeline is implemented. Image understanding and video/audio processing are planned and are not part of the current release. Because X's web experience and authentication controls can change, the browser fetcher may require maintenance over time.

Use a dedicated X account and browser profile. XListener does not solve CAPTCHAs or automate challenge flows; review the X and Telegram terms that apply to your use.

## Development

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The test suite covers configuration, parsing, context, classification, persistence, retries, Telegram workflows, supervision, and tray controls. Live X, browser-session, and local-model behavior still require Windows deployment checks.

## License

No license has been declared. Until a license is added, do not assume permission to use, modify, or redistribute this project beyond what copyright law allows.
