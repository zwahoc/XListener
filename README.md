# XListener

Local-first listener for a configurable X account, using Playwright for authenticated X access, Ollama for classification, and Telegram for notifications.

The implementation follows [XListener-detailed-build-plan.md](XListener-detailed-build-plan.md). The first code milestone is text-only monitoring with nested reply/quote/repost context, Telegram ratings, adaptive tag learning, and explicit missed-post recovery.

## Development setup

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## Local configuration

Copy `.env.example` to `.env` and set the account and Telegram values:

```text
X_MONITORED_HANDLE=thsottiaux
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

`X_MONITORED_HANDLE` accepts an optional leading `@` and overrides the account in `config.yaml`. This makes the monitored account machine-local without changing tracked configuration files.

The image/video milestone dependencies can be installed with:

```powershell
python -m pip install -e ".[dev,media]"
```

`faster-whisper` is installed with GPU support available through the detected NVIDIA device. Whisper model weights are downloaded later when a specific transcription model size is selected for the video milestone.

Runtime data belongs under `%LOCALAPPDATA%\XListener`, not in this repository.

X credentials are stored in Windows Credential Manager through `keyring` under the `XListener` service. The application will prompt for them during the one-time authentication bootstrap; do not place them in `config.yaml`, `.env`, or source files.

To store them now:

```powershell
.\.venv\Scripts\python.exe scripts\store_x_credentials.py
```

Phase 1 and Phase 2 diagnostics:

```powershell
.\.venv\Scripts\python.exe -m xlistener check
.\.venv\Scripts\python.exe -m xlistener db-status
.\.venv\Scripts\python.exe -m xlistener auth-x
.\.venv\Scripts\python.exe -m xlistener fetch-once --limit 5
```

`auth-x` opens a headed browser for the one-time login and session-state capture. `fetch-once` uses the saved state when available and falls back to public profile cards where X exposes them; replies may remain unavailable until authentication succeeds.
