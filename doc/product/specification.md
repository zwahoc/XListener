# Product Specification

## Product Statement

XListener watches one configurable X account and sends a private Telegram alert only when a local language model judges a new post relevant enough to matter. It is a personal, Windows-focused monitoring tool—not an analytics platform, public archive, or multi-user service.

## Intended User

The primary user follows an account that occasionally posts product, developer, or strategic updates. They want high-signal alerts shaped by natural-language preferences instead of a brittle keyword list, and they can rate notifications to refine local tag affinity over time.

## Functional Behavior

### Ingestion and Context

- Monitor one configured account through a dedicated authenticated Chrome profile.
- Fetch a bounded recent window of original posts, replies, and reposts.
- Include bounded parent, quote, and repost context where available.
- Treat the monitored account's own text as the primary evidence.
- Establish a first-run baseline by default to avoid notifying existing posts.
- Persist every unseen eligible post from the recent window in a durable oldest-first queue.
- Continue discovery while an earlier post is being classified or while the daemon is recovering from a pause.

### Classification

- Use a local Ollama text model.
- Return schema-validated relevance, importance (1–10), summary, reason, tags, tone, and stance.
- Apply the configured minimum importance threshold outside the model response.
- Use a selective verification pass for qualifying high-risk short relationship posts.
- Include local preferences, author context, entity context, and learned tag affinity in the decision process.
- Resolve configured product aliases and official organization handles so model updates can be recognized without requiring the words Codex or ChatGPT.

### Notification and Feedback

- Deliver qualifying posts to one configured private Telegram chat.
- Include relationship context, summary, reasoning, importance, tags, timestamps, and a source link.
- Offer inline ratings from 1 (irrelevant) to 10 (very useful).
- Store feedback locally and update bounded tag affinity when enabled.

### Recovery and Reliability

- Accept a single X or Twitter status link as a missed-post report.
- Ask for a rating before fetching or classifying the submitted post.
- Retain qualifying, failed, and user-submitted work in SQLite.
- Recover queued and retryable work after process or machine restart.
- Discard ignored post content after recording a bounded deduplication checkpoint.
- Retry failures with bounded exponential backoff and avoid reclassifying an already saved decision for delivery retries.

### Windows Operation

- Poll using a randomized configurable interval.
- Run under a Windows scheduled-task supervisor at user sign-in.
- Pause while configured game processes are active and optionally unload local models.
- Provide a Windows tray controller for status, pause/resume, supervisor control, and logs.

## Non-Goals

The current product does not provide multi-account monitoring, multi-user collaboration, a web dashboard, paid X API integration, cloud inference, a searchable archive of ignored posts, CAPTCHA automation, image understanding, video transcription, or event clustering.

## Acceptance Standard

On a supported Windows deployment, a new relevant post should travel from X retrieval through bounded context and local classification to exactly one Telegram notification. Provider interruptions and restarts should preserve enough local state to avoid silent loss and unnecessary duplicate processing.
