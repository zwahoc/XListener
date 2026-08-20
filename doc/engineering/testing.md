# Testing and Verification

XListener includes automated coverage for its core behavior, but the supported deployment is Windows 11. This repository has not been validated on macOS or Linux, and automated tests cannot guarantee that X's browser experience or authentication behavior will remain stable.

## Automated Coverage

The test suite covers:

- configuration defaults, YAML parsing, environment overrides, and validation;
- post and classification model constraints;
- X profile parser fixtures and relationship extraction;
- parent, quote, repost, and nested-context hydration;
- structured Ollama response handling and selective verification;
- SQLite retention, deduplication, cursors, retries, feedback, and tag affinity;
- Telegram rendering, message limits, callbacks, and missed-post workflows;
- daemon baseline behavior, retry flow, and instance locking;
- game-process detection, supervisor lifecycle, and tray controls.

Run the suite on a supported Windows environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Windows Deployment Checks

Before relying on an installation, verify the following on the target Windows machine:

1. `xlistener check` can reach Ollama, detect Telegram configuration, launch Chrome, and find a saved X session after authentication.
2. First-run baseline behavior does not notify existing profile content.
3. A relevant new post produces one Telegram message with the expected context and link.
4. A low-importance post is discarded after its deduplication checkpoint is recorded.
5. A rating is acknowledged in Telegram and appears in `xlistener db-status`.
6. A missed-post link asks for a rating before X fetching or model inference begins.
7. A stopped Ollama service creates retryable work rather than losing the post.
8. Sign-in starts the supervisor and tray controller without console windows.
9. A configured game pauses the daemon, and ending the game resumes it after the configured delay.

## Practical Limits

Use a soak period after changing configuration, upgrading Chrome or Playwright, or reauthenticating X. Watch for false positives, missed-post recoveries, session challenges, and unexpected restart behavior. Model judgment is probabilistic; treat notification ratings and operational logs as feedback tools, not proof of correctness.
