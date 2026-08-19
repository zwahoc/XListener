# Security and Privacy

## Credential Handling

- X credentials are stored with keyring under the XListener service and Windows Credential Manager.
- The X browser storage state is written under the local application data directory, outside Git.
- Telegram bot credentials are loaded from .env, which is ignored by Git.
- Secrets must never be placed in config.yaml, preferences files, source code, or issue reports.

## Data Boundaries

All model prompts, browser state, SQLite data, and classification results remain local except for:

1. authenticated browser requests to X;
2. Telegram Bot API requests to deliver notifications and receive feedback.

Ollama is expected to run on localhost. No tweet content is sent to a hosted LLM by the application.

## Retention

Ignored post text, context, media, and analysis are discarded immediately after the decision. Notified, failed, and user-submitted content remains in SQLite so notifications, retries, and feedback are durable. Processed-ID checkpoints expire and are capped.

## Operational Safety

- Use a dedicated X account and dedicated Chrome profile.
- Do not point XListener at an everyday Chrome profile.
- Do not automate CAPTCHA or challenge solving.
- Keep the bot chat private and verify the configured chat ID.
- Review X and Telegram terms applicable to your use.
- Treat local runtime files as sensitive; anyone with access to the Windows account may be able to inspect them.
