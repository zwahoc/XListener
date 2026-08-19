# Testing and Verification

## Automated Tests

The repository currently has 47 pytest tests covering:

- YAML, environment overrides, and default validation;
- Pydantic model bounds and model-generated tag normalization;
- HTML-safe Telegram rendering and 4096-character limits;
- SQLite retention, cursor, deduplication, retries, feedback, and learning;
- reply, quote, repost, and nested context hydration;
- Playwright parser fixtures and relationship extraction;
- malformed model responses and selective verification;
- Telegram callback and missed-post flows;
- daemon baseline, retry, cursor, and instance-lock behavior;
- gaming process detection, supervisor lifecycle, and tray controls.

Run the suite with:

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~

## Manual Acceptance Checks

Before treating a deployment as stable, verify:

1. Initial baseline does not notify old profile content.
2. A relevant new post produces exactly one Telegram message.
3. A reply includes enough parent or quote context for interpretation.
4. A low-importance post is not retained beyond its checkpoint.
5. A Telegram rating is acknowledged and persisted.
6. A missed-post link asks for a rating before X or Ollama work.
7. Stopping Ollama creates retryable work rather than data loss.
8. Windows logon starts the supervisor and tray without a console.
9. Starting a configured game pauses the daemon and unloading occurs.
10. Closing the game restarts the daemon after the configured cooldown.

## Live Test Limits

Automated tests do not prove that X will keep its DOM stable, that a session will never be challenged, or that the local model will always judge a subtle post correctly. A 24-hour soak test and periodic review of false positives and missed-post recoveries remain part of operational acceptance.
