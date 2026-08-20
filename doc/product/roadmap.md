# Roadmap

The current product is a text-first personal monitor. Future work extends media understanding and operational maturity without changing the local-first, single-user focus.

## Next: Image Understanding

Planned work includes:

1. Downloading direct and related-post images with size, MIME-type, and timeout limits.
2. Routing image-bearing context to the configured local vision model.
3. Preserving alt text and providing a text-only fallback when media is unavailable.
4. Keeping downloaded media temporary and removing it after classification.
5. Adding fixtures and Windows acceptance checks for image-led posts.

Success means a post whose important information is primarily in an image can be assessed with its relationship context intact.

## Then: Video and Audio Understanding

Planned work includes:

1. Discovering and downloading bounded video assets.
2. Extracting audio with FFmpeg.
3. Transcribing speech with a local faster-whisper model.
4. Sampling frames for visible text and visual context.
5. Combining media observations with post text and related-post context.
6. Degrading safely for missing, oversized, silent, or unsupported media.

## Operational Maturity

Near-term validation work includes Windows soak testing, reboot and sign-in checks, session-expiry recovery, and review of false positives and missed-post recoveries.

## Later Opportunities

- Broader feedback-based preference learning beyond tag affinity.
- Historical backfill when a reliable ingestion source is available.
- Optional RSS or alternative fetcher adapters behind the existing boundary.
- Event clustering across related posts.
- A read-only local diagnostics and review interface.
- Cross-platform service wrappers after Windows operation is proven stable.

## Out of Scope for the Current Direction

The roadmap does not include paid X API dependence, cloud LLM processing, automated CAPTCHA handling, or a full archive of ignored posts.
