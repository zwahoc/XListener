# Notification Format

XListener notifications are designed to be useful without duplicating the entire original post. Every delivered message includes a direct link to the source on X.

## Message Contents

```text
Original post by @account

Summary
<model-generated summary>

Reasoning from <model>
<model-generated reason>

Importance: 8/10
Tags: release, codex, limits

Posted: 21 Aug 2026, 02:36 PM MYT
Notified: 21 Aug 2026, 02:38 PM MYT

View post
```

The opening line changes with the relationship type, for example:

- `Replied by @account to @other_account`
- `Repost by @account from @other_account`
- `Missed post by @account`

Missed-post results also display the rating supplied during recovery.

## Ratings

Every normal notification includes inline buttons from 1 to 10.

- `1` means irrelevant or unwanted.
- `10` means very useful.

XListener stores the rating locally and uses it to update its bounded tag-affinity profile when learning is enabled. A rating records feedback for future decisions; it does not alter the original model decision or post content.

## Rendering Guarantees

The renderer escapes model and post text for Telegram HTML, clips individual fields, and enforces Telegram's message-length limit. Tags are model-generated, normalized to lowercase underscore identifiers, deduplicated, and limited by the classification schema; there is no fixed tag catalog.
