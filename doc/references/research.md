# Research References

The following sources informed the architecture and adapter decisions. They are references, not runtime dependencies unless listed in the engineering documentation.

| Source | Use in the design |
|---|---|
| [X API overview](https://docs.x.com/x-api/getting-started/about-x-api) | Confirmed that a paid official API is not required for the first local milestone. |
| [X developer terms](https://docs.x.com/developer-terms) | Reminder to review applicable platform terms and account risk. |
| [Nitter](https://github.com/zedeus/nitter) | Evaluated as a possible later self-hosted adapter; operational overhead is too high for the native Windows path. |
| [RSSHub](https://github.com/DIYgod/RSSHub) | Considered as a future configurable feed adapter. |
| [Playwright Python](https://playwright.dev/python/docs/intro) | Basis for persistent browser contexts and the authenticated fetcher. |
| [Ollama Windows](https://docs.ollama.com/windows) | Local service and accelerator assumptions. |
| [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) | Pydantic schema validation and low-temperature model responses. |
| [Ollama chat API](https://docs.ollama.com/api/chat) | Future multimodal routing and current local model integration. |
| [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage) | Message limits, HTML formatting, inline keyboards, and update polling. |
| [Windows schtasks](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create) | User-logon startup and restart-on-failure behavior. |
| [Qwen3 models](https://ollama.com/library/qwen3) | Initial 4B text model selection. |
| [Qwen3-VL models](https://ollama.com/library/qwen3-vl) | Planned image milestone model selection. |
| [ythx-101/x-tweet-fetcher](https://github.com/ythx-101/x-tweet-fetcher) | Reviewed for parser, ledger, and alternate-backend ideas; not used as the native authenticated X fetcher. |

The preserved [detailed build plan](detailed-build-plan.md) contains the original research notes and decision history. The preserved [project brief](original-project-brief.md) contains the initial user requirements.
