# Security and Privacy

XListener is local-first, but it handles account credentials, browser sessions, post content, and a Telegram bot token. Treat the host Windows account and its local runtime directory as trusted boundaries.

## Credentials

- X username and password are stored through `keyring` in Windows Credential Manager under the `XListener` service.
- The authenticated browser profile and saved X storage state are kept under the local runtime directory.
- Telegram credentials are read from the local `.env` file.
- Configuration templates are safe to commit; local `.env`, `config.yaml`, `preferences.yaml`, browser data, and runtime files are not.

Never include tokens, chat IDs, credentials, session data, or raw runtime logs in source code, commits, issues, pull requests, or screenshots.

## External Data Flows

Post content and related context remain on the local machine for model processing. XListener sends data externally only when required by its configured integrations:

1. The authenticated browser makes requests to X.
2. The Telegram Bot API receives notification messages and supplies feedback updates.

Ollama is configured to run on `localhost` by default. The application does not send post content to a hosted LLM.

## Retention

Ignored post text, context, and analysis are discarded after classification. XListener retains qualifying, failed, and user-submitted posts in SQLite to support delivery retries, feedback, and missed-post recovery. Processed-ID checkpoints are capped and expire according to local configuration.

Local retention does not make the runtime directory non-sensitive. Anyone with access to the Windows account may be able to read its database, logs, browser state, or configuration.

## Operational Guidance

- Use a dedicated X account and the profile created by XListener.
- Keep the configured Telegram chat private and verify its chat ID before enabling background delivery.
- Protect the Windows user account with normal OS security controls.
- Do not automate CAPTCHA or challenge solving.
- Review and comply with the X and Telegram terms that apply to your usage.
- Remove the scheduled tasks and local runtime data when decommissioning the installation.

XListener is not a security boundary, compliance system, or secret-management service. It minimizes external processing but cannot eliminate the risks of an authenticated browser session or third-party notification provider.
