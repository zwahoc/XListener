# Runtime and Data

## Runtime Directory

Windows runtime data is stored outside the repository:

~~~text
%LOCALAPPDATA%\XListener\
  xlistener.sqlite3
  xlistener.log
  supervisor.log
  xlistener.lock
  supervisor.lock
  stop.request
  pause.request
  shutdown.request
  supervisor-status.json
  browser\chrome-profile\
  secrets\x_storage.json
~~~

The exact paths can be overridden in config.yaml; environment expansion is supported.

## SQLite Retention Model

The state database contains:

- app_state: the last-seen cursor;
- processed_ids: bounded, expiring checkpoints for deduplication;
- tweets: retained qualifying, failed, or user-submitted posts;
- analyses: structured model decisions;
- notifications: confirmed Telegram deliveries;
- feedback: user ratings;
- tag_affinity and learned_profile_versions: current and historical learning summaries;
- telegram_state: the getUpdates offset;
- pending_missed_posts: link submissions awaiting a rating or completion.

Ignored posts are removed after classification. Only their ID and outcome remain in the expiring checkpoint table. This is a deliberate resource and privacy boundary, not an accidental lack of history.

## Processing States

~~~text
discovered -> classified -> notified
     |            |
     +--------> failed -> retry
ignored -> expiring processed-id checkpoint
user_submitted_missed -> classified -> notified
~~~

A qualifying post is persisted before Telegram delivery. If Telegram fails after classification, the saved analysis is reused on retry. Cursor advancement is delayed until each fetched candidate reaches a safe terminal or durable retry state.

## Locks and Control Markers

The daemon and supervisor use separate non-blocking file locks. The stop watcher observes stop.request; the tray and supervisor use pause.request and shutdown.request for cooperative lifecycle control. Marker files are local signals and contain no secrets.

## Logs

Logs rotate at approximately 5 MB with three backups. Request-library loggers are reduced to warning level so Telegram bot URLs, which may contain the bot token, are not emitted as normal request traces.
