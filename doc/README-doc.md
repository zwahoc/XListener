# XListener Documentation

Welcome to the XListener documentation. XListener is a Windows-focused, local-first service for monitoring one X account, filtering posts with a local Ollama model, and sending selected notifications to Telegram.

> Windows 11 is the supported deployment platform. macOS and Linux have not been validated.

## Getting Started

- [Installation](getting-started/installation.md) — prepare Windows, install dependencies, authenticate X, and register background startup.
- [Configuration](getting-started/configuration.md) — configure secrets, monitored account, polling, notifications, preferences, and gaming behavior.
- [Operations](getting-started/operations.md) — run diagnostics, manage the background service, inspect logs, and recover from common issues.

## Product

- [Product specification](product/specification.md) — current behavior, boundaries, and acceptance criteria.
- [Notification format](product/notification-format.md) — what Telegram messages contain and how feedback works.
- [Implementation status](product/implementation-status.md) — implemented capabilities and known limits.
- [Roadmap](product/roadmap.md) — planned image, video, and longer-term work.

## Engineering

- [Architecture](engineering/architecture.md) — component boundaries, data flow, and failure handling.
- [Runtime and data](engineering/runtime-and-data.md) — local files, persistence, retention, locks, and logs.
- [Security and privacy](engineering/security-and-privacy.md) — credentials, external data flows, and operational guidance.
- [Technology stack](engineering/tech-stack.md) — dependencies and deliberate technical constraints.
- [Testing and verification](engineering/testing.md) — automated coverage and Windows validation guidance.

## Background and References

- [Research references](references/research.md) — external documentation and projects that informed the design.
- [Design history](references/detailed-build-plan.md) — archived decisions from the initial design process.
- [Project origin](references/original-project-brief.md) — the original product brief, retained for context.

The root [README](../README.md) is the public project overview.
