# Product Specification

## Product Statement

XListener watches a configurable X account and alerts one user only when a local language model determines that a post is relevant enough to matter. It is designed for high-signal personal monitoring, not analytics, archiving, or multi-user publishing.

## Primary User

The initial user follows an OpenAI employee account for Codex and ChatGPT updates, usage-limit changes, releases, capability announcements, and meaningful replies. The user prefers model judgment over a brittle keyword list and provides explicit 1-10 usefulness ratings to improve tag affinity.

## Functional Requirements

### Ingestion

- Monitor one account selected through configuration.
- Include authored originals, replies, and reposts by default.
- Retrieve bounded parent, quoted, and reposted context.
- Preserve the monitored author's post as primary evidence.
- Use a persistent authenticated browser profile.

### Interpretation

- Use a local Ollama text model.
- Return schema-validated relevance and importance from 1 to 10.
- Generate normalized tags, narrative reasoning, summary, tone, and stance.
- Apply the configured minimum importance threshold outside the model.
- Use a skeptical second pass only for selected high-risk relationship posts.

### Notification

- Send only qualifying posts to the configured private Telegram chat.
- Include relationship line, complete summary, model reasoning, importance, tags, timestamps, and original link.
- Offer inline ratings from 1 (irrelevant) to 10 (very useful).

### Recovery and Learning

- Accept a single status URL as a missed-post report.
- Ask for the user's rating before fetching and classifying it.
- Retain notified, failed, and user-submitted items; discard ignored content after checkpointing its ID.
- Update bounded tag affinity from ratings.

### Operations

- Poll with a random 10-90 second delay.
- Retry failures with bounded exponential backoff.
- Start at user logon, pause for configured games, and expose tray controls.
- Keep running after an individual post, model, network, or Telegram failure.

## Non-Goals

The current product does not promise multi-account monitoring, a web dashboard, official paid X API integration, cloud inference, full ignored-post search, CAPTCHA solving, image understanding, video transcription, or automatic semantic event clustering.

## Acceptance Standard

The text milestone is considered usable when a new relevant post can travel from X through context hydration and local classification to exactly one Telegram notification, while restarts and provider failures preserve enough durable state to avoid silent loss or duplicate processing.
