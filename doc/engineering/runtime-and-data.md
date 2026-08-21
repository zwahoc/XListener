# Runtime and Data

XListener keeps runtime state outside the repository. On Windows, the default location is `%LOCALAPPDATA%\XListener\`.

## Runtime Files

```text
%LOCALAPPDATA%\XListener\
├── xlistener.sqlite3
├── xlistener.log
├── supervisor.log
├── supervisor-status.json
├── xlistener.lock
├── supervisor.lock
├── stop.request
├── pause.request
├── shutdown.request
├── browser\chrome-profile\
└── secrets\x_storage.json
```

Paths can be overridden in `config.yaml`; environment variables in path values are expanded during configuration loading. Treat the whole directory as local application data: it can contain browser-session material, classification results, and notification history.

## SQLite State

The SQLite database provides durable, restart-safe state:

| Data | Purpose |
|---|---|
| `app_state` | Cursor for the latest safely observed X post. |
| `processed_ids` | Bounded, expiring deduplication checkpoints. |
| `tweets` | Qualifying, failed, and user-submitted post records. |
| `analyses` | Validated model decisions and raw model responses for retained posts. |
| `notifications` | Confirmed Telegram delivery records. |
| `feedback` | Inline usefulness ratings. |
| `tag_affinity` and `learned_profile_versions` | Local preference-learning summaries and history. |
| `telegram_state` | Telegram `getUpdates` offset. |
| `pending_missed_posts` | Status-link requests awaiting a rating or completion. |

Ignored posts are not archived. After a non-qualifying decision, XListener records only the post ID and outcome in `processed_ids`, subject to the configured time and row limits. This is an intentional privacy and storage boundary.

The `tweets.status` column also acts as the durable work queue. Newly discovered posts use `queued`; classified posts use `classified`; delivery failures use `failed` with a retry timestamp. The queue is ordered by the post timestamp and first-seen time so a backlog is processed oldest-first.

## Processing and Retry Lifecycle

```text
new post → context → classification ──→ ignored checkpoint
                       │
                       └──→ retained post → Telegram notification → confirmed delivery
                                      │
                                      └──→ failure → scheduled retry
```

Qualifying posts are persisted before delivery. If Telegram fails, the next attempt reuses the saved classification. Failed classification or context work is also retained so it can be retried with exponential backoff. The cursor advances after fetched work has reached a safe terminal outcome or durable retry state.

Discovery polls a bounded 20-post window by default rather than relying only on a single latest-post cursor. This catches several posts created while the daemon was paused, gaming-aware supervision was active, or an earlier Ollama call was still running. Repeated observations are cheap ID checks and do not reclassify saved work.

## Locks and Control Markers

The daemon and supervisor use separate non-blocking locks to prevent duplicate instances. Local marker files coordinate lifecycle requests:

- `stop.request` asks the daemon to stop cooperatively.
- `pause.request` tells the supervisor to keep monitoring paused.
- `shutdown.request` asks the supervisor to exit.

`supervisor-status.json` is an atomically replaced snapshot used by the tray menu. These control files contain no secrets.

## Logging

Both application logs use rotating files: approximately 5 MB per file with three backups. The application reduces HTTP client logging to warning level to avoid normal request traces that could expose bot-token URLs.
