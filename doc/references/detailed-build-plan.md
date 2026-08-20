# Design History

This document preserves the key decisions that shaped XListener's first implementation. It is historical context, not an installation guide or a statement of future commitments. For current behavior, use the [product specification](../product/specification.md) and [implementation status](../product/implementation-status.md).

## Original Problem

The project began as a way to follow one X account without manually reading every post. The desired outcome was a private, low-cost service that could judge relevance from natural-language preferences and send only useful updates to Telegram.

## Decisions That Remain in the Product

| Decision | Rationale | Current Result |
|---|---|---|
| Monitor one account | Keep the first release simple and personally useful. | One configurable account and one private chat. |
| Use a browser-based fetcher | Avoid coupling the initial project to a paid X API. | A Playwright adapter with a dedicated authenticated Chrome profile. |
| Keep inference local | Preserve privacy and avoid hosted-model cost. | Ollama is used on localhost for text classification. |
| Use structured outputs | Make model decisions safe to store and act on. | Pydantic validation for relevance, importance, summary, tags, and interpretation fields. |
| Retain only durable work | Avoid creating a full personal archive of ignored content. | Qualifying, failed, and user-submitted posts persist; ignored posts become expiring ID checkpoints. |
| Ask before recovering a miss | Avoid expensive processing for every shared link. | Telegram requests a rating before it fetches and classifies a submitted post. |
| Separate lifecycle supervision | Make continuous use practical on a gaming laptop. | Windows Task Scheduler, a gaming-aware supervisor, and a tray controller. |

## Scope Sequence

The original plan divided delivery into three stages:

1. **Text** — retrieve posts, resolve bounded context, classify locally, notify Telegram, capture ratings, and support durable recovery.
2. **Images** — interpret direct and related-post images with a local vision model.
3. **Video and audio** — add bounded media download, local transcription, frame sampling, and multimodal synthesis.

Stage one is the current implementation. Stages two and three remain planned; see the [roadmap](../product/roadmap.md).

## Constraints Chosen for the First Release

- No paid X API requirement.
- No cloud LLM or hosted database.
- No CAPTCHA automation.
- No multi-account, multi-user, or dashboard features.
- No full archive of ignored posts.
- Windows is the target operating environment.

These constraints favored a smaller and more understandable personal tool. They may be reconsidered only when a concrete product need justifies the added complexity.
