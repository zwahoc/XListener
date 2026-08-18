# XListener Detailed Build Plan

Status: proposed for review  
Research basis: 2026-08-18  
Target: Windows 11 on the Acer Nitro AN515-58

## 1. Executive Decision

Build XListener as a small asynchronous Python daemon with four replaceable boundaries:

```text
X source -> TweetFetcher -> SQLite state -> Ollama classifier -> Telegram notifier
```

The V1 fetcher should use a dedicated authenticated Playwright Chromium profile. The user provides X credentials once through a protected local secret store; Playwright logs in during setup, saves the resulting browser state, and then reuses that state headlessly. Normal polling does not perform a login. If the cached session expires, the daemon attempts one controlled reauthentication, saves the new state, and resumes polling. This is the most practical zero-cost starting point for a single account, but it is also the least stable component, so it must be isolated behind a `TweetFetcher` protocol.

The X API should not be used for V1 because the current official documentation describes X API v2 as pay-per-usage. Nitter and RSSHub remain possible adapters, but neither should be a hard dependency for the first release.

Use SQLite from the beginning instead of a single `last_seen_tweet_id` JSON file. SQLite is still zero-configuration, but it lets the application retain retryable/notified work, feedback, learned tag affinity, Telegram offsets, and a small rolling deduplication checkpoint. Ignored posts are evaluated in memory and are not archived with their text, analysis, context, or media.

V1 will not depend on `ythx-101/x-tweet-fetcher`. We will build the authenticated `x.com` fetcher ourselves because the required credential bootstrap, persisted session, expiry detection, and controlled reauthentication flow are specific to XListener. The external repository may be consulted for implementation ideas and may later be wrapped as an optional Nitter-based fallback.

## 2. Product Definition

XListener is a personal, local-first alert daemon:

1. Monitor one configured X account.
2. Poll for recent posts approximately every 30-60 seconds.
3. Detect posts not previously processed.
4. Ask a local Ollama model whether each post matches the user's configurable interests.
5. Send only sufficiently relevant posts to one Telegram chat.
6. Analyze irrelevant posts transiently without retaining their full content.
7. Let the user submit a missed post URL and a 1-10 score later; fetch and retain that post only then.
8. Recover cleanly after process restarts, laptop restarts, network failures, and model failures.

The V1 success condition is:

> A new post from the configured account is detected, semantically classified using local inference, and delivered to Telegram when it meets the configured threshold, without a paid X or LLM API.

## 3. Research Findings

| Area | Finding | Design implication |
|---|---|---|
| Official X API | X's current documentation describes API v2 as pay-per-usage with credits deducted per request. | Do not make the official API a V1 dependency. |
| Nitter | The Nitter repository states that running an instance now requires real X accounts because Twitter removed previous access methods. It also requires Redis/Valkey and a Nim build or container. | Useful as a later self-hosted adapter, but too much operational and credential overhead for native Windows V1. |
| RSSHub | RSSHub is an active open-source RSS aggregation project with many routes and instances, but route availability and authentication requirements vary by source and deployment. | Support a configurable RSS URL later; do not assume a public Twitter route is permanently reliable. |
| Playwright | Playwright for Python supports asynchronous browser automation on Windows and persistent browser contexts. | Suitable for a dedicated login/bootstrap flow and a replaceable web fetcher. |
| Ollama on Windows | Ollama runs as a native Windows application, serves its local API on `http://localhost:11434`, and supports NVIDIA/AMD acceleration. Model storage can be moved with `OLLAMA_MODELS`. | Keep inference local and call the local HTTP/Python API. |
| Ollama structured output | Ollama supports `format: "json"` and full JSON Schema output. Its documentation recommends Pydantic schemas, low temperature, and including the schema in the prompt. | Use a Pydantic `ClassificationResult` schema and validate every response. |
| Telegram Bot API | `sendMessage` accepts a chat id, text up to 4096 characters after entity parsing, and optional Markdown/HTML formatting and inline keyboards. | Use a short HTML-formatted message and split or truncate defensively. |
| Windows Task Scheduler | `schtasks` supports `ONSTART` and `ONLOGON` triggers and can run a fully qualified command. | Run the daemon under the normal user account, with a scheduled-task registration script. |
| Local model candidates | Ollama's Qwen3 family currently includes 4B and 8B variants. The published sizes are approximately 2.5 GB and 5.2 GB respectively. | Start with `qwen3:4b`; benchmark `qwen3:8b` if the Nitro's GPU memory and latency are acceptable. |
| Vision model candidates | `qwen3:4b` is a text model. Ollama currently publishes `qwen3-vl` vision variants, including `qwen3-vl:4b` at approximately 3.3 GB, and its vision models can receive images through the chat API. | Use `qwen3-vl:4b` for tweets/replies with images; keep the text model for text-only items. |
| `ythx-101/x-tweet-fetcher` | MIT-licensed Python package with unified tweet models, Nitter/FxTwitter/browser backends, a router, and a SQLite ledger. Its timeline path is Nitter-based; its Playwright driver creates fresh contexts and fetches Nitter pages rather than persisting an authenticated `x.com` session. | Reuse as an optional Nitter adapter or parser/ledger reference, but keep the credentialed `x.com` fetcher in our own adapter. |

Sources:

- X API overview: https://docs.x.com/x-api/getting-started/about-x-api
- X developer terms index: https://docs.x.com/developer-terms
- Nitter repository and README: https://github.com/zedeus/nitter
- RSSHub repository: https://github.com/DIYgod/RSSHub
- Playwright Python introduction: https://playwright.dev/python/docs/intro
- Ollama Windows documentation: https://docs.ollama.com/windows
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Ollama chat API: https://docs.ollama.com/api/chat
- Telegram Bot API `sendMessage`: https://core.telegram.org/bots/api#sendmessage
- Windows `schtasks /create`: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create
- Ollama Qwen3 models: https://ollama.com/library/qwen3
- Ollama Qwen3-VL models: https://ollama.com/library/qwen3-vl
- `x-tweet-fetcher` repository: https://github.com/ythx-101/x-tweet-fetcher

## 4. Delivery Goals and Initial Scope

The project is divided into three sequential goals. Each goal must be stable before the next one begins.

```text
Goal 1: Text
  -> Goal 1B: Feedback capture
       -> Goal 1C: Adaptive tag learning
            -> Goal 1D: User-submitted missed posts
                 -> Goal 2: Images
                      -> Goal 3: Video
```

### Goal 1: Text-only listener

This is the first complete usable release. It monitors original posts and authored replies, extracts their available text and textual reply context, classifies them with `qwen3:4b`, and sends relevant Telegram notifications.

#### Included

- One configured X handle.
- One fetcher implementation using Playwright.
- Polling with configurable interval and small jitter.
- SQLite persistence with a durable-record boundary: notified, pending/failed, and user-submitted missed posts are retained; ignored posts are not archived.
- YAML preference configuration.
- Local Ollama classification.
- Pydantic validation of model output.
- Telegram notification delivery.
- Structured logs and health/error reporting.
- A dry-run mode that never sends Telegram messages.
- Windows setup and scheduled-task scripts.

#### Deferred to later goals

- Official paid X API access.
- Cloud LLMs or cloud hosting.
- Multiple accounts.
- A web dashboard.
- Redis, Celery, PostgreSQL, or a vector database.
- Semantic embeddings or a second-stage vector search.
- Full adaptive learning is deferred to Goal 1C.
- Daily digests.
- Cross-tweet event clustering.
- Image understanding and OCR, deferred to Goal 2.
- Video/audio transcription and frame analysis, deferred to Goal 3.
- CAPTCHA solving or account creation.

The code should preserve media URLs and metadata during Goal 1 so Goals 2 and 3 can be added without changing the fetcher or database contracts substantially.

### Goal 1B: Numeric feedback capture

Add Telegram inline buttons numbered `1` through `10`. A rating means:

- `1`: irrelevant or unwanted.
- `10`: very useful.

The listener stores the rating against the tweet, classification, tags, and relationship context. Ratings can be updated later if the user changes their mind.

### Goal 1C: Adaptive tag learning

The classifier assigns controlled tags to every processed item. Feedback updates learned affinity for those tags automatically. Future classification prompts receive the learned tag profile and representative high/low-rated examples.

The original tags on a tweet remain immutable. Feedback changes the learned affinity profile rather than rewriting history. This preserves a clear explanation of both the model's original decision and how the user's behavior influenced future decisions.

### Goal 1D: User-submitted missed posts

Ignored posts are deliberately not archived. If the user later notices an important missed post, they send the bot its X URL and a score, for example:

```text
https://x.com/.../status/... 9
```

The bot validates the URL and score, fetches the post through the authenticated X session, resolves its reply/quote/repost context, classifies and tags it, then stores the complete record as a `user_submitted_missed` item. The score is saved as feedback and immediately updates learned tag affinity. A score above 5 is treated as evidence of a false negative, but the system accepts and retains all valid scores from 1 through 10.

This flow is the intentional exception to transient ignored-post handling. It recovers useful misses without turning the listener into a full archive of everything on the monitored account.

### Goal 2: Image-aware listener

Add direct, quoted, and reply-parent image extraction. Download images temporarily and route image-bearing items through `qwen3-vl:4b`, using the same preferences and structured classification contract as Goal 1.

### Goal 3: Video-aware listener

Add X video discovery and local media processing. FFmpeg downloads/converts the media, extracts audio, and samples frames. A local Whisper implementation transcribes speech, `qwen3-vl:4b` examines selected frames and on-screen text, and the classifier combines those results with the post/reply context.

## 5. Proposed Architecture

```text
                         Windows 11 user session
                                  |
                    Task Scheduler starts `python -m xlistener`
                                  |
                       +----------v-----------+
                       | Async poll supervisor |
                       +----------+-----------+
                                  |
                  +---------------v----------------+
                  | TweetFetcher protocol          |
                  | Primary: Playwright X profile  |
                  | Optional: RSS/Nitter adapters  |
                  +---------------+----------------+
                                  |
                         recent Tweet objects
                                  |
                  +---------------v----------------+
                  | Rolling cursor/dedup checkpoint|
                  +---------------+----------------+
                                  |
                           new/unprocessed only
                                  |
                  +---------------v----------------+
                  | Classifier                     |
                  | Ollama localhost API           |
                  | Pydantic JSON Schema           |
                  +---------------+----------------+
                                  |
                         ClassificationResult
                                  |
                  +---------------v----------------+
                  | Notification policy            |
                  | relevant && importance >= N    |
                  +---------------+----------------+
                           retain only if needed
                                  |
                  +---------------v----------------+
                  | TelegramNotifier               |
                  | HTTPS Bot API                  |
                  +--------------------------------+
```

The core application must not import X-specific scraping code from the pipeline. The pipeline only consumes the `Tweet` interface.

## 6. Repository Layout

```text
twitter-listener/
|
|-- pyproject.toml
|-- README.md
|-- .env.example
|-- .gitignore
|-- config/
|   |-- preferences.example.yaml
|   `-- config.example.yaml
|-- src/
|   `-- xlistener/
|       |-- __main__.py
|       |-- cli.py
|       |-- config.py
|       |-- models.py
|       |-- db.py
|       |-- pipeline.py
|       |-- classifier.py
|       |-- notifier.py
|       |-- logging_setup.py
|       `-- fetchers/
|           |-- __init__.py
|           |-- base.py
|           |-- playwright_x.py
|           `-- rss.py
|-- tests/
|   |-- fixtures/
|   |   `-- x_profile_articles.html
|   |-- test_config.py
|   |-- test_db.py
|   |-- test_playwright_parser.py
|   |-- test_classifier.py
|   |-- test_notifier.py
|   `-- test_pipeline.py
|-- scripts/
|   |-- bootstrap_x_login.ps1
|   |-- install_windows.ps1
|   |-- register_task.ps1
|   `-- run_once.ps1
`-- data/
    `-- .gitkeep
```

Runtime data should be outside version control. A recommended Windows location is `%LOCALAPPDATA%\XListener\`, containing the database, logs, Playwright storage state, and generated runtime files. Configuration that contains no secrets can remain in the project directory.

### Initial Python dependencies

Keep the dependency set small:

```text
pydantic>=2
PyYAML
httpx
ollama
playwright
pytest
pytest-asyncio
```

`sqlite3`, `asyncio`, `logging`, and the CLI implementation should use the Python standard library. Add a retry library only if the first implementation shows that the retry policy is becoming difficult to maintain clearly.

## 7. Component Contracts

### Tweet model

```python
class MediaAsset(BaseModel):
    kind: Literal["image", "video", "gif"]
    url: AnyHttpUrl
    alt_text: str | None = None
    source: Literal["direct", "quoted", "parent"] = "direct"

class RelatedPost(BaseModel):
    relationship: Literal["reply_parent", "quoted", "reposted"]
    id: str | None = None
    author_handle: str | None = None
    text: str = ""
    url: AnyHttpUrl | None = None
    media: list[MediaAsset] = Field(default_factory=list)

class Tweet(BaseModel):
    id: str
    author_handle: str
    author_name: str | None = None
    text: str
    url: AnyHttpUrl
    created_at: datetime | None = None
    is_reply: bool = False
    in_reply_to_url: AnyHttpUrl | None = None
    media: list[MediaAsset] = Field(default_factory=list)
    is_repost: bool = False
    related_posts: list[RelatedPost] = Field(default_factory=list)
    context_complete: bool = True
    source: str
    raw_payload: dict[str, Any] = {}
```

The id is treated as an opaque string for storage, but the X adapter may use the numeric ordering of X status ids when selecting the newest post.

### Fetcher protocol

```python
class TweetFetcher(Protocol):
    async def fetch_recent(self, limit: int = 20) -> list[Tweet]: ...
```

The result must be sorted oldest-to-newest before it reaches the pipeline. A fetch failure raises a typed exception and never advances the cursor.

### Classifier contract

```python
class ClassificationResult(BaseModel):
    relevant: bool
    importance: int = Field(ge=1, le=10)
    topic: str
    tags: list[str] = Field(default_factory=list, max_length=8)
    reason: str
    summary: str
```

The classifier accepts a `Tweet`, the parsed preferences, and a bounded list of recent notification summaries. It returns only a validated `ClassificationResult`.

### Tag contract

Tags are controlled, lowercase identifiers rather than unconstrained free text. The initial vocabulary includes:

```text
codex, chatgpt, reset, quota, limits, release, update, capability,
developer_tools, availability, api, model, integration, reply, quote,
repost, marketing, meme, feedback_request, conversation, other
```

The classifier may return at most eight tags and must choose from this vocabulary. The vocabulary can grow through an explicit configuration change, but the model must not silently invent near-duplicate tags such as `limit`, `limits`, and `usage_limit`.

### Notifier contract

```python
class Notifier(Protocol):
    async def send(self, tweet: Tweet, result: ClassificationResult) -> str: ...
```

The returned string is the provider message id when available. The notifier must not log the bot token.

## 8. X Ingestion Strategy

### Primary V1: Playwright persistent browser state

The first authentication flow uses credentials once, then relies on the saved browser session:

1. `python -m xlistener auth-x` reads the X username and password from Windows Credential Manager through the Python `keyring` API. If either entry is missing, the command prompts once and saves it to the vault before continuing.
2. Playwright opens a headed Chromium window using a dedicated profile directory and submits the login flow.
3. The command verifies that the target profile is visible and saves Playwright storage state under `%LOCALAPPDATA%\XListener\secrets\x_storage.json`.
4. The daemon creates a new browser context from that storage state and runs headlessly for normal polling.
5. Before fetching, the adapter performs a lightweight authenticated-state check. If X redirects to login or the target profile is inaccessible, it attempts one reauthentication using the protected credentials.
6. After successful reauthentication, the new storage state replaces the old state. The daemon does not repeatedly log in on every poll.

If MFA, CAPTCHA, suspicious-login verification, or another interactive challenge appears, automated login pauses and reports that manual completion is required. It must not loop indefinitely or attempt to bypass the challenge.

The fetcher loads `https://x.com/<handle>`, waits for the profile/tweet region, and extracts a bounded number of `article[data-testid="tweet"]` elements. It must collect both the account's original posts and the account's authored replies to other users. If X exposes separate Posts and Replies tabs, the fetcher visits both and merges the results by tweet id. It must not treat replies written by other accounts as content from the monitored account.

For each article it should:

- Find the canonical `/status/<id>` link.
- Read visible text and the `<time datetime>` value.
- Confirm that the author handle matches the configured account.
- Detect whether the item is an original post, reply, quote post, or repost.
- Extract attached image URLs and alt text from the article, including images inside an attached quoted-tweet card when available. Label direct media versus quoted media.
- Preserve relationship URLs/ids for the direct reply parent, quoted post, or reposted original.
- For videos or GIFs, capture the poster/thumbnail URL in V1; do not download or analyze full video files yet.
- Detect repost labels where possible, but leave final relevance decisions to the classifier.
- Ignore pinned/older articles when their id is not newer than the stored cursor.
- Return multiple unseen posts oldest-to-newest, not only the newest one.

The parser must be a separate pure function so HTML snapshots can be tested without launching a browser.

### Nested-post and relationship context resolution

The LLM must not classify `@thsottiaux`'s text in isolation when it depends on another post. Before classification, a context resolver builds a labeled bundle:

```text
Monitored item
  + reply_parent, when this is a reply
  + quoted, when this is a quote post
  + reposted, when this is a repost
```

Rules:

- Reply: include `@thsottiaux`'s reply plus the full direct parent post text, author, URL, and available media.
- Quote post: include `@thsottiaux`'s commentary plus the quoted post text, author, URL, and available media.
- Repost: include the original reposted post as the substantive content, even when `@thsottiaux` added no text.
- Mixed/nested cases: resolve related posts to a maximum depth of 2 and a maximum of 3 related posts. This covers a reply to a quote or a parent post that itself quotes something without fetching an unbounded conversation thread.
- If the profile card does not contain the full related post, open its canonical status URL in the authenticated browser and parse it separately.
- Deduplicate related posts by tweet id.
- Set `context_complete: false` when an expected related post cannot be fetched. The classifier still runs with available content but is told that context is incomplete.

The classifier prompt labels every component clearly, for example `MONITORED_REPLY`, `REPLY_PARENT`, `QUOTED_POST`, and `REPOSTED_ORIGINAL`, so the model can distinguish what `@thsottiaux` wrote from what another person wrote.

### Evaluation of `x-tweet-fetcher`

The cloned public repository is a useful candidate, but it does not eliminate the need for our own authenticated fetcher:

- It exposes `Router.fetch_timeline(username, limit)` and a normalized `Tweet` dataclass.
- Its direct timeline implementation calls Nitter search (`from:<username>`), so it requires a reachable Nitter instance.
- Its optional Playwright backend renders the configured Nitter host. It does not navigate an authenticated `x.com` profile with a persisted storage state.
- Its `--monitor` mode is an incremental mentions monitor, not a monitor for every new post from one account.
- Its SQLite ledger is useful as a reference for deduplication, but our pipeline needs additional analysis, notification, retry, and failure-stage tables.
- It is MIT-licensed and has a small standard-library core, so an explicit optional adapter is technically reasonable.

Recommended use: keep `x-tweet-fetcher` out of the critical path initially. Implement `XAuthenticatedFetcher` for the credential/session design, then add an `XtfNitterFetcher` adapter only if a local or reliable Nitter instance is available. If we depend on the package, pin an exact release or commit and wrap its output into our own `Tweet` model rather than coupling the rest of the application to its schema.

### V1 dependency decision

The V1 implementation will be built without importing, vendoring, or installing `x-tweet-fetcher` as an application dependency.

We may still use the repository in three limited ways:

1. Reference its backend interface, parser-fixture tests, error categories, and deduplication ideas while designing our own components.
2. Compare its Nitter parsing behavior with our test fixtures if a Nitter fallback is explored.
3. Add a separately configured `XtfNitterFetcher` adapter after V1, without changing the classifier, state store, or notifier.

This avoids inheriting a Nitter requirement and keeps authentication/session behavior fully under XListener's control. If the repository later proves materially useful, integration remains easy because both projects already use a replaceable fetcher/backend boundary.

### Source fallback order

The application should select one source explicitly:

```yaml
fetcher:
  type: playwright_x
```

Later adapters can include:

- `rss`: a user-supplied RSS/RSSHub URL.
- `nitter`: a user-supplied, self-hosted Nitter URL.
- `curl_timeline`: a manually captured authenticated X timeline request.

Do not silently switch sources during a failure. A source change can change ordering, visibility, and authentication semantics; it should be an explicit configuration change.

### Fetching limits and gaps

- Fetch the newest 20 articles by default.
- Process every unseen article in chronological order.
- If more than 20 posts may have arrived between polls, record a `fetch_gap_suspected` warning.
- If the profile page returns no usable status links, treat the fetch as failed rather than advancing state.
- Do not mark a tweet seen merely because it was displayed by the browser; mark it only after its database record is created.

### Image acquisition

The fetcher stores media metadata and URLs, but downloads image bytes only when an item is about to be classified. The media loader should:

- Accept PNG, JPEG, and WebP images.
- Limit analysis to four direct images plus four context images per tweet/reply and enforce a configurable per-image size limit.
- Try direct download from the X image CDN first.
- If the CDN request requires the active session, fetch through the authenticated Playwright browser context.
- Validate the response MIME type before passing it to Ollama.
- Store images in a temporary runtime directory and delete them after classification unless diagnostic retention is explicitly enabled.
- Treat missing images as a recoverable degradation: classify using text, alt text, and reply context while recording that visual context was unavailable.

### Video acquisition and processing (Goal 3)

Goal 3 extends the same media boundary without changing the text or image pipelines:

1. Discover the direct MP4 or HLS playlist URL from the authenticated X page or its media/network responses.
2. Use FFmpeg to download or convert the video into a local temporary file.
3. Extract a mono 16 kHz audio track.
4. Transcribe the audio locally with `faster-whisper` or another local Whisper-compatible implementation.
5. Sample a bounded set of frames using fixed intervals or scene-change detection.
6. Send selected frames to `qwen3-vl:4b` for visual description, OCR, and UI/screenshot understanding.
7. Classify using the post/reply text, parent context, transcript, and visual summary together.

Initial safeguards:

- Maximum video duration of 10 minutes.
- Configurable download-size limit.
- Maximum of 8 sampled frames.
- No more than one video analysis at a time.
- Delete video, audio, and frame files after processing unless diagnostic retention is enabled.
- If video download or transcription fails, continue with tweet text, thumbnail, alt text, and available image context while recording incomplete media analysis.

### Account and policy risk

The saved X session and the source credentials are credentials. Prefer a dedicated account, store the username/password in Windows Credential Manager through `keyring`'s `WinVaultKeyring` backend, keep the Playwright profile private, and avoid high-frequency polling or broad scraping. The README must state that X may change its UI or restrict automated access, and that the user is responsible for complying with applicable X terms. Environment variables may be supported as an explicit development fallback, but credentials must never be written to YAML, SQLite, source code, or logs.

## 9. Persistence Design

Use one SQLite file, for example `%LOCALAPPDATA%\XListener\xlistener.sqlite3`. The schema deliberately separates durable content from lightweight deduplication state. An ignored post is classified in memory and then discarded; it is never copied into the durable content tables merely because it was seen.

### Tables

```sql
CREATE TABLE app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE processed_ids (
    tweet_id TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    outcome TEXT NOT NULL, -- retained, ignored, failed, user_submitted_missed
    expires_at TEXT
);

CREATE TABLE tweets (
    id TEXT PRIMARY KEY,
    author_handle TEXT NOT NULL,
    text TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT,
    is_reply INTEGER NOT NULL DEFAULT 0,
    in_reply_to_url TEXT,
    media_json TEXT,
    is_repost INTEGER NOT NULL DEFAULT 0,
    related_posts_json TEXT,
    context_complete INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL,
    status TEXT NOT NULL, -- discovered, classified, notified, failed, user_submitted_missed
    retention_reason TEXT NOT NULL, -- notification, retry, user_submitted_missed
    first_seen_at TEXT NOT NULL,
    processed_at TEXT,
    last_error TEXT,
    failure_stage TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TEXT
);

CREATE TABLE analyses (
    tweet_id TEXT PRIMARY KEY REFERENCES tweets(id),
    relevant INTEGER NOT NULL,
    importance INTEGER NOT NULL,
    topic TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    summary TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    raw_response TEXT
);

CREATE TABLE notifications (
    tweet_id TEXT PRIMARY KEY REFERENCES tweets(id),
    provider TEXT NOT NULL,
    provider_message_id TEXT,
    sent_at TEXT NOT NULL,
    last_error TEXT
);

CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT NOT NULL REFERENCES tweets(id),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 10),
    source TEXT NOT NULL, -- inline_button, missed_post_message
    telegram_update_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE tag_affinity (
    tag TEXT PRIMARY KEY,
    score REAL NOT NULL DEFAULT 0,
    sample_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE learned_profile_versions (
    version INTEGER PRIMARY KEY,
    profile_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE telegram_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### State rules

- `discovered`: fetched and inserted, but not yet classified.
- `classified`: a valid analysis exists; notification policy has not necessarily sent anything.
- `notified`: Telegram accepted the message.
- `failed`: processing failed and is eligible for retry.
- `user_submitted_missed`: the user supplied a post URL and score after the normal listener ignored it.

Ignored/below-threshold items are not terminal rows in `tweets`; their full text, related context, media metadata, and model response are discarded after the decision. `processed_ids` retains only a bounded, expiring id/outcome checkpoint for deduplication and cursor recovery. It contains no tweet text, media, context, model response, tags, or notification payload.

`failure_stage` distinguishes fetch-independent work such as `classification` and `notification`. If an analysis already exists, a notification retry must reuse it instead of asking the model again. Retry attempts use bounded exponential backoff and a `next_retry_at` timestamp.

The cursor is stored in `app_state` as `last_seen_id` after a successful chronological poll. `processed_ids` is a bounded safety net for duplicate or reordered results, not a historical archive. Prune it by age and count, for example after 30 days or when it exceeds 2,000 ids, whichever comes first. If a poll fails, do not advance the cursor. If the fetcher reports a gap, preserve the cursor and raise a visible warning rather than pretending all unseen posts were safely handled.

On the first run, default to `bootstrap_mode: baseline`: store the current newest post as the cursor and do not notify historical content. A `process_latest` mode is available for testing.

## 10. Configuration and Secrets

### Example configuration

```yaml
account:
  handle: thsottiaux
  profile_url: https://x.com/thsottiaux

fetcher:
  type: playwright_x
  interval_seconds: 45
  jitter_ratio: 0.15
  max_posts_per_poll: 20
  bootstrap_mode: baseline
  storage_state_path: C:/Users/<user>/AppData/Local/XListener/secrets/x_storage.json
  include_replies: true
  include_reposts: true

llm:
  model: qwen3:4b
  vision_model: qwen3-vl:4b
  base_url: http://localhost:11434
  temperature: 0
  keep_alive: "0"
  context_notifications: 5

media:
  max_images_per_tweet: 4
  max_context_images_per_tweet: 4
  max_image_size_mb: 8
  retain_downloads: false

notification:
  min_importance: 6
  chat_id_env: TELEGRAM_CHAT_ID
  parse_mode: HTML
  feedback_enabled: true
  telegram_update_poll_seconds: 2

learning:
  enabled: true
  positive_rating_min: 6
  processed_id_retention_days: 30
  processed_id_max_rows: 2000
  max_examples_in_prompt: 6

runtime:
  database_path: C:/Users/<user>/AppData/Local/XListener/xlistener.sqlite3
  log_level: INFO
  dry_run: false

interests:
  - topic: Codex resets, limits, and usage changes
    priority: high
    description: >-
      Notify me about Codex reset behavior, usage limits, quotas, reset timing,
      allowance changes, session limits, and other changes that affect how or
      when Codex can be used.

  - topic: Codex updates and releases
    priority: high
    description: >-
      Notify me about new Codex releases, product updates, version changes,
      availability changes, important fixes, breaking changes, and substantive
      announcements about the Codex product.

  - topic: Codex and ChatGPT capabilities
    priority: high
    description: >-
      Notify me when the account explains or reveals a meaningful new Codex or
      ChatGPT capability, especially coding-agent behavior, developer tooling,
      integrations, model behavior, workflows, or functionality that changes
      what I can do.

ignore:
  - Memes, jokes, and humorous posts without substantive product information
  - Generic marketing or promotional posts
  - Event promotions and announcements without a meaningful product update
  - Generic questions asking users for opinions, reactions, or feedback
  - Routine conversational replies and social commentary
  - Reposts with no meaningful new information
  - General ChatGPT or company news unrelated to Codex or a meaningful capability change
```

Telegram secrets may use environment variables or a local secrets file excluded by `.gitignore`; X credentials use Windows Credential Manager through `keyring`:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

For the actual Windows deployment, store the X username and password in Windows Credential Manager through `keyring`'s `WinVaultKeyring` backend and have the CLI read them through a small credential-provider abstraction. Use service name `XListener` with separate entries named `x_username` and `x_password`. Environment variables may be supported as an explicit development fallback, but are not the preferred long-running storage mechanism. Never commit Telegram credentials, X credentials, or Playwright storage state. The setup script should create the runtime directory and remind the user to restrict its ACLs to the current Windows account.

## 11. LLM Classification Design

### Prompt inputs

The classifier prompt contains:

1. The user's interest descriptions.
2. Ignore rules.
3. The current monitored post/reply text and metadata.
4. A labeled relationship bundle containing the direct reply parent, quoted post, or reposted original when available.
5. Attached image bytes plus media alt text from the monitored item and related posts.
6. The current learned tag-affinity profile and a small bounded set of rated examples.
7. Optionally, the last five notification summaries, truncated to a fixed character budget.
8. The output schema and decision rules.

The tweet is untrusted external content. The system prompt must explicitly say that tweet text is data to analyze, not instructions to follow. This prevents a malicious or joking tweet from changing the classifier's behavior.

### Decision policy

The model returns `relevant` and `importance`. The application, not the model, applies the notification threshold:

```python
should_notify = result.relevant and result.importance >= settings.notification.min_importance
```

This keeps policy adjustable without changing the prompt.

Recommended initial prompt rules:

- Prefer semantic meaning over exact keyword matching.
- Treat Codex reset/limit changes, releases, substantive updates, and meaningful capability explanations as strong relevance signals.
- Treat a reply as relevant when it contains new product information, clarification, availability detail, reset/limit information, release information, or a meaningful explanation of Codex/ChatGPT behavior.
- Treat memes, jokes, generic marketing, feedback questions, routine conversation, and low-information reposts as irrelevant unless they contain a material product change.
- Do not assume that every mention of ChatGPT is relevant; require a direct connection to Codex or a meaningful capability change.
- Be conservative when evidence is weak.
- Keep `summary` under 400 characters.
- `reason` should be one or two sentences.
- Do not invent facts not present in the tweet.

Initial importance calibration:

- `9-10`: direct reset, quota, availability, release, breaking-change, or major Codex capability information.
- `7-8`: meaningful new Codex/ChatGPT capability or a substantive product explanation with clear practical value.
- `6`: useful clarification or reply containing actionable information, but limited scope.
- `1-5`: memes, promotion, generic engagement questions, routine conversation, or information with no clear practical consequence.

### Ollama call

Use the official Python client or the local `/api/chat` endpoint with:

- `stream: false`.
- `format: ClassificationResult.model_json_schema()`.
- `options.temperature: 0`.
- `think: false` unless benchmarking shows that reasoning materially improves quality at an acceptable latency.
- `keep_alive: "0"` or a short duration so the laptop does not keep the model resident indefinitely while idle.

Model routing is introduced progressively:

- Goal 1 text-only tweet/reply: `qwen3:4b`.
- Goal 2 tweet/reply with one or more images: `qwen3-vl:4b`, passing the downloaded image paths or base64 image data in the message's `images` field.
- Both models receive the same preferences, decision rules, and `ClassificationResult` JSON Schema.

The first implementation should let the vision model classify directly rather than adding a separate captioning call. If evaluation shows that direct classification is inconsistent, add a fallback mode that asks `qwen3-vl:4b` for a short visual/OCR description and then sends that description to the text classifier. Only one model needs to remain loaded at a time; use a short `keep_alive` so model switching does not consume GPU memory while the listener is idle.

Validate the returned JSON with Pydantic. On invalid output, retry once with a repair prompt. If it remains invalid, retain the tweet as failed durable work and retry during a later poll; do not send a best-effort notification. For an ignored result, the validated result is used only for the current decision and then discarded. If the user later submits that URL, the system fetches and classifies it again before saving it.

### Model selection process

Start with `qwen3:4b` because the published Ollama size is about 2.5 GB. Benchmark `qwen3:8b` (about 5.2 GB) against a small local evaluation set of representative tweets:

- clear relevant product update;
- indirect semantic match;
- generic promotion;
- unrelated company news;
- low-information repost;
- ambiguous announcement;
- prompt-injection-like tweet text;
- screenshot or UI image containing Codex/ChatGPT information;
- meme image with irrelevant text;
- reply whose key information appears only in an attached image.

Select the smallest model that meets the user's precision/recall expectations and completes a classification within an acceptable latency, measured on the Nitro rather than assumed from model size.

## 12. Telegram Notification Design

Suggested message:

```text
<b>Codex update</b>

Codex added support for running multiple coding tasks in parallel.

<b>Why it matters:</b> This announces a new Codex capability.
<b>Importance:</b> 8/10
<b>Tags:</b> codex, capability, update

<a href="https://x.com/...">View tweet</a>
```

Implementation rules:

- Escape user/model text for Telegram HTML.
- Cap the rendered message below Telegram's 4096-character limit.
- Use a simple HTTPS request or a small Telegram library; do not run a local Bot API server in V1.
- Retry transient HTTP/network errors with exponential backoff.
- Treat a successful Telegram response as the point at which the notification row is marked sent.
- If a request times out after submission, record an ambiguous failure and retry cautiously; duplicate delivery is possible in that narrow case and must be documented.
- Include the immutable classifier tags in every notification so the user can see which concepts drove the decision.
- Add an inline keyboard with buttons `1` through `10`; each callback stores or updates the rating for that tweet and triggers tag-affinity learning.
- `dry_run` prints the rendered notification but never calls Telegram.
- Dry-run commands use an in-memory or temporary database and never advance the production cursor or write a terminal production status.

### Telegram feedback and missed-post intake

The daemon also polls Telegram `getUpdates` using a persisted offset in `telegram_state`. This is a separate lightweight loop from X polling and must acknowledge each update exactly once by advancing the offset after handling it.

Only updates from the configured private `chat_id` and, optionally, the configured Telegram user id are accepted. Other chats are ignored and never cause an X fetch. Inline callback data should stay compact, for example `rate:<tweet_id>:<score>`.

Supported inbound messages:

1. Inline button callback on a notification: parse the notification's `tweet_id`, validate the rating `1..10`, append a `feedback` row, update the existing feedback for display purposes, and recompute tag affinity.
2. Plain text containing an X status URL followed by a score, such as `https://x.com/user/status/123 9`: validate the URL and score, fetch that status plus bounded nested context, classify it, save it as `user_submitted_missed`, append the rating with source `missed_post_message`, and update tag affinity.

The missed-post handler must not search or persist all previously ignored posts. It fetches only the URL the user explicitly submits. Duplicate submissions for the same status update feedback and reuse the retained analysis instead of creating duplicate content rows. Scores above 5 are surfaced in logs/metrics as false-negative recovery events.

### Adaptive tag update

For each rating, compute a bounded learning delta from the 1-10 score (for example, `(rating - 5.5) / 4.5`) and apply it to every tag on the immutable analysis. Keep per-tag score, sample count, and update time in `tag_affinity`; periodically snapshot the effective profile in `learned_profile_versions`. Future prompts receive the current affinity summary and a small set of representative rated examples. The application still applies the hard delivery guardrail `relevant && importance >= 6`; learned affinity influences model judgment, not the safety of delivery policy.

## 13. Main Processing Loop

```python
async def run_forever() -> None:
    await dependencies.check_ollama()
    await dependencies.check_telegram()  # skipped in dry-run
    await bootstrap_if_needed()

    feedback_task = asyncio.create_task(run_telegram_updates())

    while True:
        started = monotonic()
        try:
            tweets = await fetcher.fetch_recent(limit=settings.max_posts_per_poll)
            for tweet in tweets:  # already oldest -> newest
                if db.was_recently_processed(tweet.id):
                    continue
                try:
                    result = await classifier.classify(
                        tweet=tweet,
                        preferences=config.preferences,
                        learned_profile=db.current_learned_profile(),
                        recent_notifications=db.recent_notification_context(limit=5),
                    )

                    if not (result.relevant and result.importance >= settings.notification.min_importance):
                        db.record_processed_id(tweet.id, outcome="ignored")
                        continue

                    db.retain_for_notification(tweet, result)
                    if settings.runtime.dry_run:
                        print(render_notification(tweet, result))
                        continue

                    message_id = await notifier.send(tweet, result)
                    db.mark_notified(tweet.id, message_id)
                except Exception as exc:
                    db.retain_failed(tweet, stage=current_stage(), error=str(exc))
                    log.exception("tweet processing failed for %s", tweet.id)

            await retry_durable_failures()
            db.advance_cursor_after_completed_batch(tweets)
            db.prune_processed_ids()

        except FetchError as exc:
            log.warning("fetch failed: %s", exc)
        except Exception:
            log.exception("poll failed")

        await asyncio.sleep(next_interval(started))
```

Important ordering decisions:

- Fetch all currently unseen posts in chronological order.
- Classify each new item in memory. If ignored, persist only its id/outcome checkpoint and discard all full content and analysis objects.
- Before notification, retain the tweet and analysis durably. If classification or notification fails, retain the tweet as retryable work before moving on.
- Record the processed-id checkpoint for retained and failed items as well as ignored items, while keeping the full content only in the durable `tweets` path.
- Advance the batch cursor only after every item in that fetched batch has reached one of three safe outcomes: ignored checkpoint, durable notification work, or durable failed work.
- Never advance state on fetch failure.
- Reuse an existing analysis when retrying only the notification stage.
- Retry failed rows before or alongside newly fetched rows, with a bounded retry count and a visible error log.
- Run Telegram inbound handling concurrently and persist the `getUpdates` offset only after an update is handled.
- Run `--dry-run` against an isolated temporary store so it cannot consume or suppress a real notification.

## 14. Error Handling and Recovery

### X/browser failures

- Browser launch failure: log a clear setup message and retry with backoff.
- Session expired: mark the fetcher unhealthy and tell the user to rerun `auth-x`; do not repeatedly submit login forms.
- CAPTCHA or challenge: stop automated interaction and require manual user action.
- Changed selectors: parser returns no tweets, health check fails, and an HTML snapshot is optionally saved for diagnosis.
- Rate limiting: increase backoff and keep the last cursor unchanged.

### Ollama failures

- Connection refused: log that Ollama is not running; retry later.
- Model missing: log the exact `ollama pull <model>` command.
- Timeout: retry with a longer timeout once, then keep the tweet in `failed` state.
- Invalid JSON: repair once, then fail safely.

### Telegram failures

- 4xx configuration errors: do not retry indefinitely; log the response category and keep the tweet failed.
- 429 or 5xx/network errors: exponential backoff with a maximum delay.
- Ambiguous timeout after send: record it separately from a confirmed failure.

The process should continue polling after an individual tweet failure. A single bad item must not stop the daemon.

## 15. Windows Installation and Operation

### Prerequisites

- Windows 11.
- Python 3.11 or newer.
- Git.
- Ollama for Windows.
- A Chromium browser installed by Playwright.
- A Telegram account and bot token.

### Setup sequence

1. Clone or copy the project into a stable directory such as `C:\XListener`.
2. Create a Python virtual environment and install the project plus Playwright browsers.
3. Install Ollama and pull the selected model.
4. Create `config.yaml` from the example and fill in the monitored handle and preferences.
5. Create a bot with BotFather, start a private chat with it, and determine the target chat id.
6. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the user's environment or a protected local secrets file.
7. Run `python -m xlistener auth-x`; it prompts once for missing X credentials and stores them in Windows Credential Manager through `keyring`. Complete any MFA or challenge manually if X presents one.
8. Run `python -m xlistener check` to validate config, database access, X session, Ollama, and Telegram.
9. Run `python -m xlistener once --dry-run` and inspect the parsed tweet and model decision.
10. Run `python -m xlistener once` with a test notification.
11. Register the scheduled task.

### Scheduled task

Register a task such as `XListener` with:

- Trigger: `ONLOGON` for the normal user, plus a manual recovery shortcut.
- Optional `ONSTART` trigger if the machine must run before user login.
- Action: the fully qualified path to the virtual-environment Python executable and `-m xlistener`.
- Working directory: the project directory.
- Run as the normal user account, not `SYSTEM`, because the task needs the user's protected browser state and user-level environment.
- Restart on failure with a short delay.
- Write stdout/stderr to rotating log files.

The laptop should remain plugged in with sleep disabled while plugged in. Display sleep is fine. Ollama model residency should be short-lived so idle power use remains low.

## 16. CLI Surface

Implement a small CLI so setup and diagnosis do not require editing Python:

```text
python -m xlistener auth-x       # credential bootstrap, challenge handling, and storage-state capture
python -m xlistener check        # dependency and configuration checks
python -m xlistener once         # one fetch/classify/notify cycle
python -m xlistener once --dry-run
python -m xlistener run          # continuous daemon
python -m xlistener db-status    # cursor and recent processing state
```

## 17. Testing Strategy

### Unit tests

- YAML parsing, defaults, and missing-secret validation.
- Pydantic classification schema bounds.
- Telegram HTML escaping and message length limits.
- SQLite durable-retention boundary, rolling dedupe checkpoints, cursor advancement, and status transitions.
- Feedback rating validation, duplicate-rating behavior, tag-affinity updates, and learned-profile snapshots.
- Telegram `getUpdates` offset handling and missed-post URL/score parsing.
- X HTML parser with saved fixtures.
- Pinned tweet and repost handling.
- Direct, quoted, and parent image URL extraction.
- Media download limits, MIME validation, and cleanup.
- Chronological ordering and cursor comparisons.

### Integration tests

- Mock Ollama HTTP responses: valid JSON, malformed JSON, timeout, 500 response.
- Mock Ollama vision requests with image payloads and verify text/vision model routing.
- Mock Telegram HTTP responses: success, 429, 400, timeout.
- Mock Telegram inbound updates: inline rating callback, malformed score, duplicate update, and URL-plus-score missed-post submission.
- End-to-end pipeline with fixture tweets and fake classifier/notifier.
- Restart after classification failure and notification failure, including retry without reclassification when analysis exists.

### Manual acceptance tests

Goal 1 - text and relationship context:

1. Baseline mode does not notify old profile content.
2. A new relevant tweet produces exactly one Telegram message.
3. A new irrelevant tweet produces no message.
4. An irrelevant post leaves no durable tweet text, analysis, media, or context row; only a bounded id checkpoint remains.
5. A semantically matching tweet without exact keywords is classified correctly.
6. A repost with no meaningful information is ignored.
7. A reply whose meaning depends on its parent post is classified with the direct parent's text.
8. A quote post is classified with both `@thsottiaux`'s commentary and the quoted post.
9. A repost is classified using the reposted original, including when `@thsottiaux` added no text.
10. A nested reply-to-quote resolves context within the configured depth/quantity limits.
11. Restarting the daemon does not reprocess a retained terminal tweet or duplicate a notification.
12. Stopping Ollama causes a retryable durable failure, not data loss.
13. Invalidating the X session produces a clear re-authentication instruction.
14. The daemon remains alive after one tweet or provider failure.
15. A Telegram rating updates the feedback row and changes affinity for the tweet's tags.
16. Sending `https://x.com/.../status/... 9` causes only that URL to be fetched, classified, retained as `user_submitted_missed`, and rated; previously ignored posts remain unarchived.
17. A malformed URL or score is rejected without a fetch or database write.
18. A 24-hour soak test shows stable memory use and no repeated notifications.

Goal 2 - images:

1. A reply whose information exists only in an attached image is classified correctly.
2. A reply with a useful image in its parent/quoted tweet retains that context for classification.
3. An unavailable image falls back to text and alt text without losing the tweet.

Goal 3 - video:

1. A video with spoken Codex information is classified using its transcript.
2. A silent screen recording is classified using sampled frames and on-screen text.
3. An unavailable or oversized video degrades to post text, thumbnail, and available context.

## 18. Delivery Milestones

### Milestone 0: Ingestion feasibility spike

Deliver a script that opens the dedicated Playwright profile, reads the target profile page, and prints the newest 5 parsed tweets.

Exit criteria:

- Manual login works.
- The parser extracts stable ids, text, URLs, and timestamps.
- The parser extracts direct, quoted, and reply-parent media metadata where available.
- Pinned posts and repost labels are understood well enough for V1.
- A changed or unavailable session fails visibly.

### Milestone 1: Project skeleton and persistence

Add configuration, models, SQLite schema, logging, CLI, and fixture-based tests.

Exit criteria:

- `check`, `once`, and `db-status` work without Ollama or Telegram.
- Duplicate tweet ids are harmless.
- Restart recovery is covered by tests.

### Milestone 2: Text classifier and transient decision path

Add the text-only prompt, Pydantic schema, local API client, learned-profile input, timeout/retry behavior, dry-run output, and the rule that ignored items are discarded after classification.

Exit criteria:

- A representative local test set yields valid JSON on every case.
- Invalid responses are rejected safely.
- Ignored items leave only a bounded id checkpoint; relevant items are retained before notification.
- Model latency is measured on the Nitro.

### Milestone 3: Telegram notifier and numeric feedback

Add secrets loading, HTML-safe formatting with tags, inline 1-10 buttons, `getUpdates` offset persistence, retry policy, and dry-run mode.

Exit criteria:

- A test message arrives in the private chat.
- No secret appears in logs.
- Notification rows are recorded only after confirmed success.
- A button rating is persisted and visible in `db-status`.
- Telegram updates resume correctly after a restart without replaying handled updates.

### Milestone 4: Adaptive tag learning and missed-post recovery

Add controlled-tag affinity updates, learned-profile snapshots, rated examples in prompts, and URL-plus-score missed-post intake.

Exit criteria:

- Ratings 1 and 10 push tag affinity in opposite directions.
- A rating can be updated without duplicating the durable tweet.
- A submitted missed post is fetched, context-resolved, classified, tagged, retained, and linked to its rating.
- The system never scans or archives all historical ignored posts during missed-post recovery.

### Milestone 5: End-to-end text daemon

Connect the real fetcher, database, classifier, notifier, feedback loop, and missed-post handler.

Exit criteria:

- A real new post follows the full path to Telegram.
- An irrelevant post is not retained beyond the minimal checkpoint.
- A restart does not duplicate a terminal event.

### Milestone 6: Image-aware listener

Add image download/cleanup and `qwen3-vl:4b` routing for direct, quoted, and parent images.

Exit criteria:

- Image-only information in a monitored or nested post can affect classification.
- Missing or oversized images degrade to text and alt text without breaking the loop.

### Milestone 7: Video-aware listener

Add FFmpeg extraction, local transcription, sampled-frame vision analysis, and bounded cleanup.

Exit criteria:

- Spoken and on-screen Codex information can affect classification.
- Oversized or unavailable video degrades safely.

### Milestone 8: Windows operational hardening

Add setup scripts, scheduled-task registration, log rotation, health checks, and a 24-hour soak test.

Exit criteria:

- The process starts after login/reboot as designed.
- Logs make outages diagnosable without opening the source.
- The laptop remains mostly idle between polls.

### Milestone 9: Optional adapters

Only after V1 is stable, add RSS, self-hosted Nitter, or a manually captured cURL timeline source and run the same contract tests against each adapter.

## 19. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| X changes DOM or blocks automated sessions | No new tweets are detected | Isolate parser, save fixtures, add health checks, keep adapter interface, use a dedicated account. |
| Session expires or CAPTCHA appears | Fetching stops | Manual `auth-x` flow; never automate CAPTCHA; notify via logs and provide a recovery command. |
| Polling misses more posts than the page limit | Missed alerts | Fetch 20 by default, warn on suspected gaps, add a later historical/backfill adapter. |
| Small model misclassifies posts | False positives/negatives | Curated evaluation set, conservative prompt, adjustable threshold, retain notified/retry analyses for review, and learn from explicit ratings. |
| Relevant post is initially ignored | Missed alert | Do not archive every ignored post; provide explicit URL-plus-score recovery, reclassify the submitted post, retain it, and update tag affinity from the user's rating. |
| Ollama model consumes too much VRAM/RAM | Slow or unstable laptop | Start at 4B, benchmark 8B, set short keep-alive, move model storage if needed. |
| Telegram request times out after delivery | Duplicate notification on retry | Record ambiguous state, keep messages short, document the narrow duplicate risk. |
| Secrets leak through repo or logs | Account/bot compromise | Runtime directory outside repo, `.gitignore`, environment variables, redacted logs, restricted ACLs. |
| X terms or account enforcement risk | Account disruption | Low polling rate, narrow scope, dedicated account, user review of applicable policies. |
| Laptop sleeps, reboots, or loses network | Temporary monitoring gap | Scheduled task restart, retry backoff, persisted state, Windows power configuration. |

## 20. Decisions for Review Before Coding

### Confirmed

- Monitor the X account `@thsottiaux`.
- Monitor both original posts and replies authored by `@thsottiaux`.
- Use automated credential bootstrap with credentials stored in Windows Credential Manager.
- Reuse the saved X session and reauthenticate only when it expires.
- Use baseline mode on first startup, so existing posts are not immediately notified.
- Use a dedicated X account for the automation.
- Start with `qwen3:4b`; benchmark `qwen3:8b` later if useful.
- Use `importance >= 6` as the initial application notification threshold. The LLM still decides relevance and produces the importance score from the user's preferences; this threshold is only the final delivery guardrail.
- Use SQLite and local Playwright session state.
- Start the daemon after the Windows user logs in (`ONLOGON`).
- Retain full local tweet and analysis history only for notified, retryable/failed, and user-submitted missed posts; do not archive ignored posts.
- Retain only a bounded, expiring processed-id checkpoint for ignored posts so resource use does not grow with the account's entire history.
- Allow Telegram inline ratings from 1 (irrelevant) to 10 (very useful), and allow URL-plus-score submissions to recover missed posts.
- Use the initial Codex-focused preference draft in this document and refine it after observing real classifications.

### Still needed

No remaining decision blocks the start of implementation. The interest and ignore rules should be refined iteratively after reviewing real examples from `@thsottiaux`.

All major V1 architecture and configuration decisions are settled.
