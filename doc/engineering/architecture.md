# Architecture

## Design Goals

XListener is intentionally a small local daemon rather than a hosted platform. The design optimizes for:

- one monitored X account;
- local inference with no cloud LLM dependency;
- durable recovery after process, network, Telegram, or Ollama failures;
- explicit control over what content is retained;
- replaceable provider boundaries when X changes its web interface.

## System Boundary

~~~text
                         +----------------------+
                         | Windows Task Scheduler|
                         +----------+-----------+
                                    |
                            +-------v--------+
                            | GamingSupervisor|
                            +---+--------+---+
                                |        |
                       pause/stop|        |status
                                |        v
                       +--------v--+  tray.py
                       | TextDaemon |
                       +-----+------+
                             |
           +-----------------+------------------+
           |                 |                  |
    PlaywrightXFetcher  OllamaTextClassifier  Telegram
           |                 |                  |
           v                 v                  v
           X web         qwen3:4b          Bot API / chat
           |
           v
       SQLiteState
~~~

The arrows represent application contracts, not shared database access. The daemon owns the polling and feedback loops; the supervisor owns the daemon process lifecycle; the tray only writes control markers and reads a status file.

## Components

### Configuration

config.py loads YAML, .env, and platform defaults into Pydantic settings. X_MONITORED_HANDLE is an environment override so the tracked repository never dictates the local account. Runtime paths are expanded into the Windows local application data directory.

### X fetcher

PlaywrightXFetcher owns the persistent Chrome profile, authenticated session bootstrap, profile-page parsing, and post retrieval. It extracts original posts, replies, reposts, quoted posts, timestamps, and available media metadata. ContextResolver hydrates a bounded relationship graph so a reply is interpreted with its parent or quoted post without crawling an entire thread.

The fetcher is an adapter boundary. X DOM and session behavior can change without forcing changes to persistence, classification, or Telegram delivery.

### Text daemon

TextDaemon runs one serialized polling work lock:

1. retry due durable failures;
2. fetch a bounded recent window;
3. compare IDs with the SQLite cursor and deduplication table;
4. hydrate reply, quote, and repost context;
5. classify unseen posts oldest-first;
6. discard ignored content after recording only an expiring ID checkpoint;
7. retain qualifying content before sending it;
8. deliver Telegram notifications and record confirmed message IDs;
9. advance the cursor only after safe outcomes are recorded;
10. wait a fresh random delay between 10 and 90 seconds.

Telegram updates are consumed concurrently with X polling. A shared work lock prevents a missed-post request from mutating the same state while a normal tweet is being processed.

### Classifier

OllamaTextClassifier builds a structured prompt from:

- the monitored author profile;
- the four products of interest;
- interest priorities and ignore guidance;
- an 11-organization competitor glossary;
- explicit reply-first and tone/stance rules;
- learned tag affinity and bounded rated examples.

The model returns a Pydantic-validated ClassificationResult with relevance, importance, topic, model-generated tags, tone, stance, summary, and narrative reasoning. High-risk short replies with an unexpectedly high score receive a selective second pass for skepticism. The verifier may lower or correct the first result; it does not perform web search.

### Telegram

TelegramNotifier renders an HTML-safe, length-bounded message and attaches inline ratings from 1 to 10. TelegramFeedbackConsumer uses long polling with a durable update offset. The same consumer accepts a status link as a missed-post report, asks for a rating, then fetches and classifies only that submitted post.

### Supervisor and tray

GamingSupervisor detects configured process names using Windows tasklist. It stops the daemon cooperatively, unloads the configured Ollama models, and restarts after a cooldown when gaming ends. It also recovers from daemon crashes.

tray.py is a separate pystray process. It never owns the daemon lock or database connection. Pause, shutdown, and resume are communicated through marker files; current state is published as a small JSON status file.

## Failure Isolation

Failures are scoped to the smallest possible unit:

- a malformed post does not stop the polling loop;
- an Ollama failure creates retryable durable work;
- a Telegram failure reuses saved analysis instead of invoking Ollama again;
- an expired X session enters an authentication cooldown;
- a crashed daemon is restarted by the supervisor or Task Scheduler;
- ignored content is not retained merely to make recovery possible later.
