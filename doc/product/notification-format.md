# Notification Format

Notifications are deliberately informative without duplicating the entire tweet. The original post remains one tap away through View tweet.

~~~text
Original post by @thsottiaux

Summary
<complete model summary>

Reasoning from qwen3:4b
<narrative model reasoning>

Importance: 9/10
Tags: codex, reset, release

Timestamp
Posted: 19 Aug 2026, 02:36 PM MYT
Notified: 19 Aug 2026, 08:38 PM MYT

View tweet
~~~

Replies and reposts use relationship-specific opening lines, for example Replied by @thsottiaux to @user or Repost by @thsottiaux from @user. Missed-post results use Missed post by @thsottiaux and include the user's rating alongside model importance.

The renderer escapes HTML, clips long model fields, and enforces Telegram's 4096-character message limit. Tags come from the model and are normalized to lowercase underscore identifiers; the application does not impose a fixed tag vocabulary.
