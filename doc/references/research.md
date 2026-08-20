# Research References

The following sources informed XListener's design. They are reference material, not runtime dependencies unless they are also listed in the [technology stack](../engineering/tech-stack.md). Availability, pricing, terms, and product behavior can change; consult the linked primary source before making an operational decision.

| Source | Why it informed the design |
|---|---|
| [X API overview](https://docs.x.com/x-api/getting-started/about-x-api) | Context for the decision not to require the official API in the initial local implementation. |
| [X developer terms](https://docs.x.com/developer-terms) | Reminder to review the platform terms that apply to browser-based use. |
| [Playwright for Python](https://playwright.dev/python/docs/intro) | Browser automation and persistent-context patterns for the authenticated fetcher. |
| [Ollama for Windows](https://docs.ollama.com/windows) | Local model service installation and Windows runtime context. |
| [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) | Schema-guided model output and validation approach. |
| [Ollama chat API](https://docs.ollama.com/api/chat) | Local model interaction and future multimodal design context. |
| [Telegram Bot API](https://core.telegram.org/bots/api) | Private-message delivery, inline keyboards, callbacks, and update polling. |
| [Windows scheduled tasks](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create) | User-logon startup and lifecycle management reference. |
| [Qwen3 on Ollama](https://ollama.com/library/qwen3) | Default local text-model family. |
| [Qwen3-VL on Ollama](https://ollama.com/library/qwen3-vl) | Future local vision-model direction. |
| [Nitter](https://github.com/zedeus/nitter) | Evaluated as a possible alternative ingestion path, not used by the current fetcher. |
| [RSSHub](https://github.com/DIYgod/RSSHub) | Evaluated as a potential future feed adapter. |
| [x-tweet-fetcher](https://github.com/ythx-101/x-tweet-fetcher) | Reviewed for adapter and persistence ideas; not used in the current authenticated X flow. |

The [design history](detailed-build-plan.md) summarizes how this research influenced the initial product boundaries.
