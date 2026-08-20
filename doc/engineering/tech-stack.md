# Technology Stack

XListener uses a deliberately compact Windows-oriented stack. The goal is a local, understandable personal service rather than a distributed platform.

| Layer | Technology | Role |
|---|---|---|
| Application | Python 3.11–3.14 | Core runtime and CLI. |
| Concurrency | `asyncio` and `TaskGroup` | X polling and Telegram feedback handling. |
| Configuration | Pydantic, PyYAML, python-dotenv | Validated local configuration and environment overrides. |
| X access | Playwright with Google Chrome | Dedicated authenticated browser session and page parsing. |
| Persistence | SQLite | Cursor, deduplication, retries, retained records, feedback, and learning state. |
| Local inference | Ollama and `qwen3:8b` | Structured text classification on the local machine. |
| Notifications | Telegram Bot API via httpx | Private delivery, ratings, and missed-post requests. |
| Credential storage | keyring / Windows Credential Manager | X username and password storage. |
| Windows lifecycle | Task Scheduler and `pythonw.exe` | User-logon startup without a console window. |
| Tray interface | pystray and Pillow | Local service controls and status. |
| Testing | pytest and pytest-asyncio | Unit and async behavior coverage. |

## Deliberate Constraints

The current text release intentionally excludes:

- paid X API access;
- cloud LLMs and hosted databases;
- multi-account or multi-user operation;
- dashboards, queues, vector databases, or distributed workers;
- automated CAPTCHA or account-creation flows;
- a full archive of ignored posts;
- image, video, and audio understanding.

These are scope decisions, not statements that the excluded technologies are never useful. They keep the project private, low-cost, and practical to operate on one supported Windows machine.

## Provider Boundaries

The core flow depends on focused interfaces rather than broad provider coupling:

- the fetcher provides X posts and bounded context;
- the classifier returns a validated decision;
- the notifier and feedback consumer handle Telegram interaction;
- `SQLiteState` owns durable local state.

This separation makes fixture-based testing possible and leaves room for future ingestion adapters without rewriting product logic.
