# X / Twitter Listener with LLM-Based Personal Filtering

## Project Goal

Build a **zero-cost personal X / Twitter listener** that monitors one public X account.

Whenever the monitored account publishes a new tweet:

1. Detect the new tweet.
2. Send the tweet content to a local LLM.
3. Give the LLM a description of what information I care about.
4. Let the LLM reason about whether the tweet is relevant to me.
5. If it is relevant, send me a notification through Telegram.
6. If it is not relevant, silently ignore it.

The system should use **zero paid APIs** and prioritize free, self-hosted, and local tools. The intended host for V1 is my **Windows Acer Nitro AN515-58 gaming laptop**, which can remain powered on and plugged in.

---

## Example

My interests might contain instructions such as:

- Look for Codex update news.
- Look for major OpenAI developer-tool announcements.
- Look for new model releases.
- Look for important API changes.
- Ignore ordinary promotional posts.
- Ignore unrelated company news.
- Ignore reposts that contain no meaningful new information.

A new tweet arrives:

> Codex now supports a new feature for running multiple coding tasks in parallel.

The LLM receives both:

### My Preferences

```text
I want to know about:
- Codex updates
- Important OpenAI developer-tool updates
- New coding-agent functionality
- Important API or model releases

I usually do not care about:
- Marketing posts
- Event promotions
- Generic company announcements
```

### New Tweet

```text
Codex now supports a new feature for running multiple coding tasks in parallel.
```

The LLM reasons that this tweet is related to a topic I care about and returns something like:

```json
{
  "relevant": true,
  "importance": 8,
  "topic": "Codex",
  "reason": "This announces a new Codex capability.",
  "summary": "Codex added support for running multiple coding tasks in parallel."
}
```

The application then sends the notification to me.

If the tweet is unrelated, the LLM might return:

```json
{
  "relevant": false,
  "importance": 2,
  "topic": "Other",
  "reason": "This does not match the user's tracked interests.",
  "summary": ""
}
```

No notification is sent.

---

# Core Architecture

```text
                    ┌─────────────────┐
                    │  X / Twitter    │
                    │ monitored user  │
                    └────────┬────────┘
                             │
                       polling/checking
                             │
                             ▼
                    ┌─────────────────┐
                    │  Tweet Fetcher  │
                    │     Python      │
                    └────────┬────────┘
                             │
                        new tweet?
                             │
                             ▼
                    ┌─────────────────┐
                    │ Deduplication   │
                    │ last tweet ID   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Local LLM     │
                    │     Ollama      │
                    └────────┬────────┘
                             │
                    reason using my
                       preferences
                             │
                    ┌────────┴────────┐
                    │                 │
               relevant          irrelevant
                    │                 │
                    ▼                 ▼
             ┌─────────────┐        ignore
             │  Telegram   │
             │     Bot     │
             └─────────────┘
```

---

# Recommended Free Local Technology Stack

## Application

**Python**

Responsibilities:

- Fetch the latest tweet.
- Detect whether it is new.
- Call the local LLM.
- Parse the LLM response.
- Send notifications.
- Store state.

---

## Tweet Collection

Avoid the paid official X API initially.

Possible free approaches:

1. Nitter / RSS-compatible source
2. RSSHub
3. Public X page scraping
4. Playwright-based browser automation as a fallback

The tweet source should be isolated behind a `TweetFetcher` component so it can be replaced easily if one method stops working.

Example interface:

```python
tweet = fetcher.get_latest_tweet()
```

The rest of the application should not care whether the tweet came from Nitter, RSSHub, Playwright, or another source.

---

## Polling

Because X does not provide a free webhook for this use case, the application periodically checks for new tweets.

Initial interval:

```text
30-60 seconds
```

For one monitored account, this is sufficient.

Example:

```python
while True:
    check_for_new_tweet()
    await asyncio.sleep(30)
```

---

# LLM

Use a local model through **Ollama**.

Possible models:

- Qwen
- Gemma
- Llama
- Other small instruction-following models

The task does not require a very large model.

The LLM mainly performs:

```text
tweet
+
my preferences
+
recent notification context
        ↓
reasoning
        ↓
should I be notified?
```

---

# Personal Interest Configuration

My interests should be configurable rather than hard-coded into Python.

Example:

```yaml
interests:
  - topic: Codex
    priority: high
    description: >
      Notify me about new Codex features, releases,
      capabilities, major changes, availability,
      integrations, pricing changes, and developer updates.

  - topic: OpenAI developer tools
    priority: high
    description: >
      Important updates involving APIs, SDKs,
      coding agents, developer platforms and tools.

  - topic: AI model releases
    priority: medium
    description: >
      Important new models or major upgrades.

ignore:
  - Generic marketing posts
  - Event promotions
  - Hiring announcements
  - Reposts with no meaningful new information
```

This configuration is included in the LLM prompt whenever a new tweet is analyzed.

---

# LLM Decision Format

The model should return structured JSON instead of free-form text.

Example:

```json
{
  "relevant": true,
  "importance": 8,
  "topic": "Codex",
  "reason": "The tweet announces a new Codex feature.",
  "summary": "Codex added a new parallel task capability."
}
```

Suggested fields:

| Field | Purpose |
|---|---|
| `relevant` | Whether I care about this tweet |
| `importance` | Importance score, e.g. 1-10 |
| `topic` | Which interest category matched |
| `reason` | Why the LLM thinks it matters |
| `summary` | Short notification-ready summary |

Notification rule example:

```python
if result["relevant"] and result["importance"] >= 6:
    send_notification()
```

---

# Notification

Use a **Telegram Bot** initially.

Why:

- Free
- Easy API
- Fast
- Works well for personal notifications
- Supports links, formatting, buttons, and images

Example notification:

```text
🔔 Codex Update

Codex added support for running multiple coding
tasks in parallel.

Why this matters:
New Codex functionality matched your tracked interests.

Importance: 8/10

View Tweet:
https://x.com/...
```

Email can be added later for daily summaries.

WhatsApp is not a priority because the official solution is more complicated and may incur charges.

---


# Hosting Environment

V1 will run entirely on my **Windows laptop** rather than a cloud server.

Intended machine:

```text
Acer Nitro AN515-58
Windows
```

The laptop is currently mainly used for gaming, while my MacBook remains my primary workstation.

The Nitro will also act as a small local AI/server machine.

```text
Acer Nitro
│
├── Windows
│
├── Python listener
├── Ollama
│   └── local LLM
├── Telegram notifier
├── state/database
└── future local automation services
```

## Why Use the Nitro

The Twitter monitoring process itself is extremely lightweight.

Most of the time the application will simply:

```text
poll source
→ detect no new tweet
→ sleep
```

The GPU or heavier compute is only needed when a new tweet arrives and the local LLM performs inference.

Because only one X account is being monitored, LLM usage should be very occasional.

This makes the Nitro suitable for running the project continuously without needing paid cloud hosting.

---

## Windows Runtime

Initial software:

```text
Windows 11
Python
Ollama for Windows
Git
VS Code
```

The project should run natively on Windows initially.

WSL2, Docker, or Linux containers are not required for V1.

They can be introduced later if the project grows into a larger home-server or personal-assistant environment.

---

## 24/7 Operation

The laptop may remain powered on and plugged in continuously.

Recommended configuration:

- Disable automatic sleep while plugged in.
- Allow the display to turn off normally.
- Enable an Acer battery charge limit such as 80% if supported.
- Keep the laptop well ventilated.
- Avoid blocking the intake or exhaust vents.
- Allow Ollama models to unload when inactive rather than keeping the GPU busy continuously.

Conceptually:

```text
Python listener
     │
     │ mostly idle
     │
     ├── no tweet → sleep
     │
     └── new tweet
            ↓
         Ollama
            ↓
       local inference
            ↓
       relevant?
            ↓
         Telegram
            ↓
         idle again
```

The machine does not need to perform continuous AI inference.

---

## No Cloud Requirement

V1 should **not depend on cloud hosting**.

Do not require:

- AWS
- Google Cloud
- Azure
- Oracle Cloud
- Paid VPS
- Paid GPU hosting
- Paid LLM APIs

All processing should remain on the Nitro unless a free external service is explicitly needed for obtaining tweets or delivering notifications.

The goal is:

> **Run the full listener and AI filtering pipeline locally for RM0/month.**

---

# State Storage

For the first version, use either:

- JSON file
- SQLite

Minimum required state:

```json
{
  "last_seen_tweet_id": "1234567890"
}
```

SQLite can be introduced when more information needs to be stored.

Possible future tables:

```text
tweets
analysis
notifications
preferences
feedback
```

---

# Suggested Project Structure

```text
twitter-listener/
│
├── main.py
├── fetcher.py
├── classifier.py
├── notifier.py
├── preferences.yaml
├── state.json
├── requirements.txt
└── README.md
```

### `main.py`

Main application loop.

### `fetcher.py`

Retrieves the latest tweet from the monitored account.

### `classifier.py`

Sends the tweet and my preferences to Ollama and parses the response.

### `notifier.py`

Sends Telegram notifications.

### `preferences.yaml`

Stores what I care about.

### `state.json`

Stores the last processed tweet ID.

---

# Main Processing Flow

Pseudo-code:

```python
while True:

    latest_tweet = fetch_latest_tweet()

    if latest_tweet.id != last_seen_tweet_id:

        result = llm.analyze(
            preferences=my_preferences,
            tweet=latest_tweet
        )

        if result.relevant:
            send_telegram(
                tweet=latest_tweet,
                analysis=result
            )

        save_last_seen_tweet_id(latest_tweet.id)

    await asyncio.sleep(30)
```

---

# Important Design Principle

The LLM should not simply perform keyword matching.

For example, if my preference says:

```text
Look for Codex update news.
```

The tweet does **not** have to contain exactly:

```text
"Codex update"
```

The LLM should understand meaning.

Example tweet:

```text
You can now delegate several software-engineering tasks
to Codex simultaneously.
```

Even though the phrase `Codex update` does not appear, the LLM should recognize that this is a Codex product update and notify me.

This is why the LLM acts as a **semantic and reasoning-based personal information filter**.

---

# Future Improvements

Once the basic version works, possible improvements include:

## Duplicate Event Detection

Avoid notifying me repeatedly when several tweets discuss the same event.

```text
Tweet A → Codex releases feature X → notify

Tweet B → talks about the same feature → ignore

Tweet C → reveals an important new detail → notify
```

---

## Feedback

Telegram messages could include:

```text
👍 Useful
👎 Not useful
```

The system records feedback and gradually improves the preference profile.

---

## Multiple Accounts

Later:

```yaml
accounts:
  - OpenAI
  - OpenAIDevs
  - another_account
```

The same LLM filtering pipeline can process all of them.

---

## Different Notification Priorities

Example:

```text
importance 9-10
→ notify immediately

importance 6-8
→ normal Telegram message

importance 3-5
→ include in daily digest

importance 1-2
→ ignore
```

---

## Context Awareness

The LLM can eventually consider:

- Previous tweets
- Previous notifications
- Previously identified events
- My feedback
- Changing preferences

This would make the system increasingly behave like a personal information-monitoring assistant rather than a simple keyword alert.

---

# Version 1 Scope

The first version should stay intentionally small and run locally on the Windows Nitro.

Build only:

1. Monitor one public X account.
2. Poll for new tweets.
3. Store the last processed tweet ID.
4. Run each new tweet through a local Ollama model.
5. Provide my configured preferences to the LLM.
6. Receive structured relevance output.
7. Send relevant tweets through Telegram.
8. Ignore irrelevant tweets.
9. Run continuously on the Windows Acer Nitro laptop.
10. Use only free/local components for the core system.

Do not initially add:

- Redis
- Celery
- PostgreSQL
- Vector databases
- Complex web dashboards
- Paid X APIs
- Cloud LLM APIs
- Paid cloud hosting
- Paid X APIs

The goal of V1 is to prove that:

> A new tweet can automatically be detected, understood in the context of my personal interests, and selectively delivered to me without using paid services.
