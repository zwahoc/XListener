# XListener Documentation

XListener is a local-first listener for one configurable X account. It retrieves posts through an authenticated browser session, interprets them with a local Ollama model, and sends selected notifications to Telegram.

## Start Here

- [Installation](getting-started/installation.md) - install dependencies and prepare a Windows machine.
- [Configuration](getting-started/configuration.md) - configure the monitored account, preferences, secrets, and runtime behavior.
- [Operations](getting-started/operations.md) - authenticate, run diagnostics, inspect logs, and control background monitoring.

## Product

- [Product Specification](product/specification.md) - user-facing behavior and acceptance criteria.
- [Implementation Status](product/implementation-status.md) - what is implemented and what remains.
- [Roadmap](product/roadmap.md) - the staged path from text to image and video understanding.
- [Notification Format](product/notification-format.md) - Telegram message structure and rating behavior.

## Engineering

- [Architecture](engineering/architecture.md) - component boundaries and end-to-end processing flow.
- [Technology Stack](engineering/tech-stack.md) - dependencies, provider choices, and tradeoffs.
- [Runtime and Data](engineering/runtime-and-data.md) - SQLite, retention, locks, logs, and local runtime files.
- [Security and Privacy](engineering/security-and-privacy.md) - credential handling and data boundaries.
- [Testing](engineering/testing.md) - test layers and operational verification.

## References

- [Research References](references/research.md) - external projects and documentation that informed decisions.
- [Detailed Build Plan](references/detailed-build-plan.md) - the original design plan and decision record.
- [Original Project Brief](references/original-project-brief.md) - the initial product brief.

The root [README](../README.md) is the public project overview and quick-start page.
