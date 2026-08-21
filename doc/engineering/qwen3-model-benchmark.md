# Qwen3 Thinking-Mode Benchmark

## Purpose

This benchmark compares `qwen3:4b` and `qwen3:8b` for one identical XListener classification task. The goal is to evaluate practical processing time and output quality before choosing the default model.

## Test conditions

- Test post: [2090766694897619318](https://x.com/thsottiaux/status/2090766694897619318)
- Source: the already stored SQLite tweet record, including its quoted context
- Prompt: the production XListener classifier prompt
- Context: the same author context, competitor glossary, interests, learned tag affinity, recent summaries, schema, temperature, and keep-alive settings
- Thinking: forced with `think=True`
- Verification: enabled when the classifier's selective verifier requires it
- Delivery: disabled; no Telegram message was sent
- Persistence: benchmark results were not written to the tweet's saved analysis
- Hardware state: the daemon was paused during testing to avoid GPU contention, then restored

## Results

| Model | Context run | Result | First pass | Verification | Total |
|---|---:|---|---:|---:|---:|
| `qwen3:8b` | 40,960 tokens | Completed valid structured output | 271.46 s | Not used | **271.46 s** |
| `qwen3:4b` | Default 262,144 tokens | No valid response before 600-second timeout | >600 s | Not reached | **Timeout** |
| `qwen3:4b` | Matched 40,960 tokens diagnostic run | No valid response before 600-second timeout | >600 s | Not reached | **Timeout** |

The 4b process was stopped after each timeout so it could not continue consuming CPU/GPU resources. Its default Ollama allocation reported a 262,144-token context. A second diagnostic run explicitly used 40,960 tokens—the context reported for the 8b run—and it still exceeded ten minutes. This indicates that the observed problem is not explained only by the larger default context allocation.

## 8b output

**Importance:** 9/10

**Summary:**

> OpenAI employee Tibo announces Codex has reached 20M active users and will credit all Codex and ChatGPT Work users with a BANKED reset. The post clarifies that sub2api usage (converting subscriptions to API traffic) is flagged by fraud-prevention systems and advises using official clients for subscription-based usage. The update emphasizes user growth, reset credits, and security measures while acknowledging ongoing investigations into unusual usage patterns.

**Reasoning:**

> This post confirms a major Codex reset event tied to reaching 20M active users, with explicit mention of BANKED reset credits and clarification on sub2api fraud detection. The fraud prevention context and reset policy changes directly align with high-priority interests in usage limits, reset mechanics, and security measures. The community engagement aspect highlights OpenAI's communication strategy around product updates.

The fields were materially different and the reasoning justified the score rather than merely repeating the summary.

## 4b output

No usable 4b classification output was produced in either run. Because the model did not return a validated JSON result within ten minutes, there is no fair 4b summary/reasoning quality comparison for this hardware and prompt.

## Interpretation

Under these conditions, `qwen3:8b` is currently the practical choice. It completed the task in about 4 minutes 31 seconds and produced a valid, distinct summary and reasoning. `qwen3:4b` was not faster in thinking mode; it failed to complete within the ten-minute benchmark limit even when given the same 40,960-token context.

This is a local hardware/runtime observation, not a claim that 4b is universally slower. Ollama version, GPU offload, model settings, prompt length, and system load can change the result. A future 4b test could be useful with a shorter context, non-thinking mode, or different GPU allocation, but that would no longer be the same high-context thinking comparison requested here.

## Runtime state after benchmark

The manual pause marker was removed and the Windows supervisor restarted the daemon. No source, model configuration, database analysis, commit, or push was changed by this benchmark.
