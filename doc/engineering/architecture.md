# Architecture

XListener is a small, single-user Windows service. Its architecture prioritizes local inference, durable delivery, clear retention boundaries, and replaceable X ingestion rather than scale or multi-tenant features.

## System Overview

```text
Windows Task Scheduler
          │
          ▼
  GamingSupervisor ────────────────► system tray
          │                              │
          ▼                              │ status and controls
      TextDaemon ◄───────────────────────┘
       │    │    │
       │    │    └────────────► Telegram Bot API
       │    └──────────────────► Ollama on localhost
       └───────────────────────► authenticated X session
                         │
                         ▼
                    SQLite state
```

The daemon owns polling, durable state, classification, delivery, and Telegram feedback. The supervisor owns the daemon process lifecycle. The tray controller uses local marker and status files; it does not access the application database or daemon lock directly.

## Main Components

### Configuration

`config.py` merges local YAML configuration, `.env` values, and safe defaults into validated Pydantic settings. `X_MONITORED_HANDLE` overrides the YAML account, allowing the tracked repository to remain independent of a local monitoring target. Runtime paths default to `%LOCALAPPDATA%\XListener\` on Windows.

### X Fetcher and Context Resolver

`PlaywrightXFetcher` owns a dedicated persistent Chrome profile, manual authentication, session reuse, profile-page parsing, and retrieval of a bounded recent window. It identifies original posts, replies, reposts, quoted posts, timestamps, and available media metadata.

`ContextResolver` enriches a post with bounded parent, quote, and repost context. Configured entity aliases can clarify the subject of a related post, but the classifier is instructed to treat the monitored account's text as the primary evidence.

The fetcher is an adapter boundary. X page or session changes should be isolated to this layer rather than changing persistence, classification, or Telegram delivery.

### Text Daemon

Each polling cycle is serialized by a work lock:

1. Retry due durable failures.
2. Fetch and order a bounded window of recent posts.
3. Establish a first-run baseline or identify posts newer than the cursor.
4. Enrich unseen posts with relationship context.
5. Classify each candidate and apply the delivery threshold.
6. Retain qualifying or failed work; discard ignored content after recording an expiring ID checkpoint.
7. Deliver qualifying notifications and record confirmed Telegram message IDs.
8. Advance the cursor and prune old checkpoints.

Telegram feedback polling runs alongside X polling. A shared work lock ensures a user-submitted missed-post request cannot alter the same state while normal processing is in progress.

### Local Classifier

`OllamaTextClassifier` builds a structured prompt from local preferences, monitored-author context, related-post context, interpretation rules, learned tag affinity, and a bounded set of rated examples. The local model returns a Pydantic-validated `ClassificationResult` containing relevance, importance, summary, reason, tags, tone, and stance.

A selective verification pass is used for high-risk short relationship posts that receive unexpectedly high scores. It can correct or reduce a first-pass result; it does not perform web research.

### Telegram Integration

`TelegramNotifier` renders an HTML-safe, length-bounded message and attaches 1–10 rating buttons. `TelegramFeedbackConsumer` uses Telegram long polling with a durable update offset to record ratings and accept missed-post links.

For a missed post, XListener requests a rating first. Only after the rating is supplied does it fetch, classify, and persist the linked post.

### Supervisor and Tray

`GamingSupervisor` detects configured executable names with Windows `tasklist`. It starts the daemon, stops it cooperatively while a configured game is active or a manual pause is requested, optionally unloads Ollama models, and restarts after a cooldown. It also records small status snapshots for the tray controller.

`tray.py` provides local pause, resume, supervisor, and log controls through `pystray`. It communicates through marker files and does not own the application process.

## Failure Handling

Failures are contained at the smallest practical boundary:

- A malformed or unclassifiable post becomes retryable durable work instead of stopping the service.
- Failed Telegram delivery reuses saved analysis; it does not call Ollama again.
- An unavailable X session enters the configured authentication cooldown.
- The supervisor can restart a crashed daemon.
- Ignored post content is intentionally not retained solely to make later recovery possible.

See [Runtime and data](runtime-and-data.md) for storage and retention details.
