# XListener

Local-first, privacy-conscious monitoring for a configurable X account.

XListener retrieves posts through a dedicated authenticated Chrome profile, uses a local Ollama model to decide what matters, and sends concise, rated notifications to Telegram. It is designed for one user, one monitored account, and high-signal personal awareness.

> Current support: Windows 11. The text milestone is implemented; image and video understanding are planned.

## What It Does

- Monitors original posts, replies, reposts, and bounded parent/quote context.
- Uses local Qwen inference with structured, validated output.
- Reasons about relevance, importance, tone, stance, and model-generated tags.
- Applies a selective skeptical verifier to high-risk short replies.
- Sends Telegram messages with complete summaries, narrative reasoning, Malaysia-time timestamps, and a View tweet link.
- Accepts 1-10 usefulness ratings and learns bounded tag affinity.
- Recovers missed posts from a user-submitted X status link.
- Retries durable failures without rerunning Ollama when analysis is already saved.
- Runs continuously through a windowless Windows supervisor and system tray.
- Pauses polling while configured games are active and unloads Ollama models to reduce GPU use.

## Architecture

~~~text
X account
   |
   v
PlaywrightXFetcher -> ContextResolver -> SQLiteState
                                      |
                                      v
                              OllamaTextClassifier
                                      |
                                      v
                              TelegramNotifier
                                      ^
                                      |
                         TelegramFeedbackConsumer

Task Scheduler -> GamingSupervisor -> TextDaemon
                              ^
                              |
                         Tray controller
~~~

Ignored posts are not archived. Only an expiring ID checkpoint is retained. Qualifying, failed, and user-submitted posts are retained so notification, retry, and feedback workflows survive restarts.

## Quick Start

~~~powershell
git clone https://github.com/zwahoc/XListener.git
Set-Location XListener
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
ollama pull qwen3:4b
Copy-Item .env.example .env
Copy-Item config/config.example.yaml config.yaml
Copy-Item config/preferences.example.yaml preferences.yaml
~~~

Set the values in .env, store X credentials, authenticate the dedicated browser profile, then install background startup:

~~~powershell
.\.venv\Scripts\python.exe scripts/store_x_credentials.py
.\.venv\Scripts\python.exe -m xlistener auth-x --manual
.\.venv\Scripts\python.exe -m xlistener check
powershell -ExecutionPolicy Bypass -File scripts/install_xlistener_task.ps1
~~~

The installer registers XListener Supervisor and XListener Tray. Both run through pythonw.exe, so monitoring does not require an open terminal.

## Documentation

The complete documentation is organized under doc/:

- [Installation](doc/getting-started/installation.md) - prerequisites, package setup, authentication, and startup registration.
- [Configuration](doc/getting-started/configuration.md) - environment variables, YAML settings, preferences, and game triggers.
- [Operations](doc/getting-started/operations.md) - diagnostics, background control, logs, and recovery.
- [Architecture](doc/engineering/architecture.md) - system boundaries and processing flow.
- [Technology Stack](doc/engineering/tech-stack.md) - dependencies and design tradeoffs.
- [Runtime and Data](doc/engineering/runtime-and-data.md) - persistence, retention, locks, and logs.
- [Security and Privacy](doc/engineering/security-and-privacy.md) - local data and credential boundaries.
- [Product Specification](doc/product/specification.md) - behavior and acceptance criteria.
- [Implementation Status](doc/product/implementation-status.md) - completed, pending, and deferred capabilities.
- [Roadmap](doc/product/roadmap.md) - image and video milestones.
- [Research References](doc/references/research.md) - sources and evaluated alternatives.

## Useful Commands

~~~powershell
.\.venv\Scripts\python.exe -m xlistener check
.\.venv\Scripts\python.exe -m xlistener db-status
.\.venv\Scripts\python.exe -m xlistener gaming-status
.\.venv\Scripts\python.exe -m xlistener fetch-once --limit 5
.\.venv\Scripts\python.exe -m xlistener classify-latest
.\.venv\Scripts\python.exe -m xlistener notify-latest --dry-run
~~~

Use the tray menu for normal pause, resume, supervisor, and log controls. The daemon should not be launched separately while the supervisor is installed and running.

## Development

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~

The suite currently covers parser fixtures, relationship context, model validation and verification, SQLite durability, Telegram workflows, retries, supervisor lifecycle, and tray controls.

## Project Status

The text listener is the first usable product milestone. Image understanding is next, followed by video/audio extraction and transcription. Broader feedback-based preference learning, historical backfill, cross-account monitoring, dashboards, and cloud providers remain deferred.

X's web interface and authentication behavior can change. XListener does not automate CAPTCHA solving and should be operated with a dedicated account and profile. Review the applicable X and Telegram terms before deployment.

## License

No license has been declared yet. Until one is added, the repository should be treated as source-available for personal use rather than as a permissively licensed library.
