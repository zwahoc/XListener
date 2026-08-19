# Roadmap

## Current Release: Goal 1A Text Listener

The text pipeline is complete enough for continuous personal use. Remaining work is operational confidence: a 24-hour soak, logout/reboot verification, and occasional review of missed-post recoveries and false positives.

## Next: Goal 2 Image Understanding

Planned work:

1. Download direct, quoted, and parent images with size, MIME, and timeout limits.
2. Route image-bearing context to qwen3-vl:4b.
3. Include alt text and a text-only fallback when an image is unavailable.
4. Keep image files temporary and clean them after classification.
5. Add fixture and manual acceptance tests for image-only information.

Success means a reply whose meaning exists primarily in an attached image can be classified with the relationship context intact.

## Then: Goal 3 Video Understanding

Planned work:

1. Detect and download bounded video assets.
2. Extract audio with FFmpeg.
3. Transcribe spoken content with a local faster-whisper model.
4. Sample frames for screen text and visual context.
5. Combine transcript, sampled-frame observations, post text, and nested context.
6. Degrade safely when media is unavailable, oversized, silent, or unsupported.

## Later Enhancements

- Broader feedback-based preference learning beyond tag affinity.
- Historical backfill when a reliable source adapter exists.
- Optional RSS/Nitter adapters behind the fetcher contract.
- Better event clustering across related posts.
- A read-only local dashboard for diagnostics and review.
- Cross-platform service wrappers after Windows operation is stable.

## Explicitly Deferred

The project will not add a paid X API, cloud LLM calls, CAPTCHA automation, or a full archive of every ignored post as part of the current roadmap.
