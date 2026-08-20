# Project Origin

This page preserves the original product intent in a public-friendly form. It is background context, not a replacement for the current [product specification](../product/specification.md).

## Initial Goal

Create a private listener for one X account that:

1. Detects newly published posts.
2. Evaluates them against the user's interests using a local language model.
3. Sends a Telegram notification only when the post is useful.
4. Silently ignores ordinary, irrelevant, or low-value content.

The initial vision favored free or self-hosted components and a Windows laptop that could remain online for continuous monitoring.

## Example Decision

Given a preference for meaningful coding-agent, API, or model updates, a post announcing a substantive capability change should receive a high relevance and importance score. A generic promotion, meme, or routine conversational reply should normally be suppressed.

The core idea has remained the same: use model judgment and user preferences to reduce noise without relying only on rigid keywords.

## How the Idea Evolved

The implementation added several safeguards beyond the original brief:

- persistent browser-session authentication and bounded relationship context;
- structured, schema-validated classifier output;
- durable retries and delivery records;
- Telegram ratings and local tag-affinity learning;
- user-driven missed-post recovery;
- Windows lifecycle supervision and gaming-aware pausing;
- explicit privacy boundaries for ignored posts.

For the implemented feature set, start with the [README](../../README.md) or the [documentation index](../README.md).
