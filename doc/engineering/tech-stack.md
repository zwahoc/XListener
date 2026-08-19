# Technology Stack

## Runtime

| Layer | Technology | Role |
|---|---|---|
| Language | Python 3.11-3.14 | Application runtime |
| Async runtime | asyncio and TaskGroup | Concurrent polling and Telegram handling |
| Configuration | Pydantic 2, PyYAML, python-dotenv | Validated settings and local overrides |
| Browser access | Playwright for Python with installed Google Chrome | Authenticated X retrieval |
| Persistence | SQLite via the standard library | Cursor, dedupe, durable work, feedback, and learned tag affinity |
| Local inference | Ollama HTTP/Python client | Text classification with qwen3:8b |
| Notifications | Telegram Bot API through httpx | Private-chat delivery and inline feedback |
| Secrets | keyring and Windows Credential Manager | X username/password storage |
| Windows lifecycle | Task Scheduler and pythonw.exe | User-logon startup without a console |
| Tray UI | pystray and Pillow | Status and lifecycle controls |
| Test runner | pytest and pytest-asyncio | Unit and async integration tests |

## Deliberate Non-Choices

- No paid X API dependency in the text milestone.
- No cloud LLM or hosted database.
- No web dashboard, Redis, Celery, PostgreSQL, or vector database.
- No CAPTCHA solver or automated account creation.
- No full historical archive of ignored posts.

These constraints keep the first release inexpensive, private, and operable on one Windows laptop. They are not claims that these technologies could never be useful in a later multi-user deployment.

## Model Routing

The active text model is qwen3:8b. It is approximately 5.2 GB and is used with partial CPU/GPU offloading on the development laptop's 4 GB RTX 3050. The configuration names qwen3-vl:4b as the future vision model, but image and video processing are not yet part of the production pipeline. Video transcription is planned around faster-whisper and FFmpeg after the image milestone.

## Provider Contracts

The core pipeline depends on protocols rather than concrete provider internals:

- TweetFetcher for X ingestion;
- classifier client methods for local inference;
- Telegram notifier/client methods for outbound and inbound messages;
- SQLiteState for durable state.

This makes fixture tests fast and allows later RSS, Nitter, or alternative browser adapters without rewriting product logic.
