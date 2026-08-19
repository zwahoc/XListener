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

XListener uses a dedicated persistent Google Chrome profile under the local runtime directory (`browser/chrome-profile`). Run `auth-x --manual` for the initial login. It opens ordinary Google Chrome without Playwright attached; complete the login and close that dedicated Chrome window so XListener can verify the session automatically. The same profile will be reused on later fetches. Do not point it at your everyday Chrome profile.

Normal monitoring will choose a new random delay between 10 and 90 seconds after each X poll. Authentication failures and service errors use separate, longer cooldowns rather than this normal range.

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
.\.venv\Scripts\python.exe -m xlistener classify-latest
.\.venv\Scripts\python.exe -m xlistener notify-latest --dry-run
.\.venv\Scripts\python.exe -m xlistener feedback-once
```

`auth-x --manual` opens the dedicated installed-Chrome profile as an ordinary browser process for the one-time login, then verifies and captures the session after you close it. `fetch-once` reuses that persistent profile and falls back to public profile cards where X exposes them; replies may remain unavailable until authentication succeeds. Google Chrome must be installed for the manual bootstrap.

`classify-latest` fetches the newest item, resolves a bounded reply/quote/repost context bundle, and asks the local Ollama text model for a schema-validated relevance decision. It prints the result locally and does not send a Telegram notification or persist ignored content.

`notify-latest` applies the configured relevance threshold and sends qualifying posts with a compact Telegram message containing the relationship line, complete model summary, narrative reasoning, importance, tags, Malaysia-time timestamps, and a link to the original post. Inline rating buttons run from 1 (irrelevant) to 10 (very useful). Successful notifications are retained in SQLite before feedback can be accepted. `feedback-once` consumes pending private-chat button callbacks once and persists both the rating and Telegram update offset.
