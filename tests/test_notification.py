import html
from datetime import datetime, timezone

import httpx
import pytest

from xlistener.config import load_settings
from xlistener.db import SQLiteState
from xlistener.missed_posts import MissedPostOutcome
from xlistener.models import ClassificationResult, RelatedPost, Tweet
from xlistener.notification import (
    NotificationError,
    TelegramFeedbackConsumer,
    TelegramNotifier,
    normalize_missed_post_url,
    parse_missed_rating_callback,
    parse_rating_callback,
    rating_keyboard,
    render_notification,
    should_notify,
)


def tweet() -> Tweet:
    return Tweet(
        id="100",
        author_handle="thsottiaux",
        text="Codex <now> has a reset update.",
        url="https://x.com/thsottiaux/status/100",
        related_posts=[
            RelatedPost(
                relationship="reply_parent",
                author_handle="someone",
                text="What changed?",
                url="https://x.com/someone/status/90",
            )
        ],
        source="test",
    )


def result(**overrides) -> ClassificationResult:
    values = {
        "relevant": True,
        "importance": 8,
        "topic": "Codex update",
        "tags": ["codex", "update"],
        "reason": "A useful product change.",
        "summary": "Codex changed reset behavior.",
    }
    values.update(overrides)
    return ClassificationResult(**values)


def test_threshold_is_applied_outside_model(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")

    assert should_notify(result(importance=6), settings)
    assert not should_notify(result(importance=5), settings)
    assert not should_notify(result(relevant=False), settings)


def test_render_notification_escapes_html_and_includes_context() -> None:
    posted = datetime(2026, 8, 19, 1, 47, tzinfo=timezone.utc)
    notified = datetime(2026, 8, 19, 2, 3, tzinfo=timezone.utc)
    message = render_notification(
        tweet().model_copy(update={"created_at": posted, "is_reply": True}),
        result(),
        model_name="qwen3:4b",
        notified_at=notified,
    )

    assert "Replied by" in message
    assert "@thsottiaux" in message
    assert "@someone" in message
    assert "<b>Summary</b>" in message
    assert "Reasoning from qwen3:4b" in message
    assert "Codex changed reset behavior." in message
    assert "Codex &lt;now&gt;" not in message
    assert "What changed?" not in message
    assert "Posted: 19 Aug 2026, 09:47 AM MYT" in message
    assert "Notified: 19 Aug 2026, 10:03 AM MYT" in message
    assert "https://x.com/thsottiaux/status/100" in message
    assert len(message) <= 4096
    assert html.unescape(message).count("Codex") == 1


def test_render_notification_is_capped(tmp_path) -> None:
    long_tweet = tweet().model_copy(update={"text": "x" * 5000})

    message = render_notification(long_tweet, result(summary="x" * 5000), max_length=300)

    assert len(message) == 300
    assert message.endswith("...")


def test_rating_keyboard_and_callback_parser() -> None:
    keyboard = rating_keyboard("100")

    assert [button["text"] for row in keyboard["inline_keyboard"] for button in row] == [str(i) for i in range(1, 11)]
    assert parse_rating_callback("rate:100:7") == ("100", 7)
    assert parse_rating_callback("rate:100:11") is None
    assert parse_missed_rating_callback("miss:abc123:8") == ("abc123", 8)
    assert normalize_missed_post_url("https://twitter.com/user/status/123?ref_src=test") == "https://x.com/user/status/123"
    assert normalize_missed_post_url("https://example.com/user/status/123") is None


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeTelegramClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


async def test_notifier_sends_message_and_retries_transient_error(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.telegram_bot_token = "token"
    settings.telegram_chat_id = "123"
    client = FakeTelegramClient([httpx.ReadTimeout("timeout"), {"ok": True, "result": {"message_id": 42}}])

    async with TelegramNotifier(settings, client=client, sleep=lambda _seconds: _noop()) as notifier:
        message_id = await notifier.send(tweet(), result())

    assert message_id == "42"
    assert len(client.calls) == 2
    assert client.calls[0][0] == "/sendMessage"
    assert client.calls[1][1]["json"]["chat_id"] == "123"
    assert client.calls[1][1]["json"]["reply_markup"]["inline_keyboard"][1][-1]["text"] == "10"


async def _noop() -> None:
    return None


async def test_notifier_rejects_below_threshold(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.telegram_bot_token = "token"
    settings.telegram_chat_id = "123"
    client = FakeTelegramClient([])

    with pytest.raises(NotificationError, match="below the notification threshold"):
        await TelegramNotifier(settings, client=client).send(tweet(), result(importance=2))


async def test_feedback_consumer_persists_rating_and_offset(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.telegram_bot_token = "token"
    settings.telegram_chat_id = "123"
    client = FakeTelegramClient(
        [
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 50,
                        "callback_query": {
                            "id": "callback-1",
                            "data": "rate:100:9",
                            "message": {"chat": {"id": 123}},
                        },
                    }
                ],
            },
            {"ok": True, "result": True},
        ]
    )
    with SQLiteState(tmp_path / "state.sqlite3") as db:
        db.retain_tweet(tweet(), "notification")
        async with TelegramFeedbackConsumer(settings, db, client=client) as consumer:
            handled = await consumer.poll_once()

        row = db.connection.execute("SELECT rating, telegram_update_id FROM feedback WHERE tweet_id = '100'").fetchone()
        assert handled == 1
        assert (row["rating"], row["telegram_update_id"]) == (9, "50")
        assert db.get_telegram_offset() == 51
        assert client.calls[1][0] == "/answerCallbackQuery"


class FakeMissedRecovery:
    def __init__(self):
        self.calls = []

    async def process(self, url, rating):
        self.calls.append((url, rating))
        return MissedPostOutcome(
            tweet=tweet().model_copy(update={"url": url}),
            result=result(),
            rating=rating,
        )


async def test_feedback_consumer_prompts_then_recovers_link_only_missed_post(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.telegram_bot_token = "token"
    settings.telegram_chat_id = "123"
    link = "https://x.com/thsottiaux/status/200"
    client = FakeTelegramClient(
        [
            {"ok": True, "result": [{"update_id": 60, "message": {"chat": {"id": 123}, "text": link}}]},
            {"ok": True, "result": {"message_id": 1}},
        ]
    )
    recovery = FakeMissedRecovery()
    with SQLiteState(tmp_path / "state.sqlite3") as db:
        async with TelegramFeedbackConsumer(settings, db, client=client, missed_recovery=recovery) as consumer:
            assert await consumer.poll_once() == 1

        request = db.connection.execute("SELECT * FROM pending_missed_posts").fetchone()
        assert request["url"] == link
        assert client.calls[1][1]["json"]["text"] == "How useful is this missed post?"
        callback_data = client.calls[1][1]["json"]["reply_markup"]["inline_keyboard"][1][2]["callback_data"]
        assert callback_data == f"miss:{request['request_id']}:8"

        callback_client = FakeTelegramClient(
            [
                {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 61,
                            "callback_query": {
                                "id": "callback-2",
                                "data": callback_data,
                                "message": {"chat": {"id": 123}},
                            },
                        }
                    ],
                },
                {"ok": True, "result": True},
                {"ok": True, "result": {"message_id": 2}},
                {"ok": True, "result": {"message_id": 3}},
            ]
        )
        async with TelegramFeedbackConsumer(settings, db, client=callback_client, missed_recovery=recovery) as consumer:
            assert await consumer.poll_once() == 1

        assert recovery.calls == [(link, 8)]
        assert db.get_missed_post_request(request["request_id"])["status"] == "completed"
        assert "Processing missed post" in callback_client.calls[2][1]["json"]["text"]
        assert "Missed post by" in callback_client.calls[3][1]["json"]["text"]
        assert "Your rating" in callback_client.calls[3][1]["json"]["text"]


async def test_missed_post_request_completes_only_after_confirmation_delivery(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.telegram_bot_token = "token"
    settings.telegram_chat_id = "123"
    recovery = FakeMissedRecovery()
    with SQLiteState(tmp_path / "state.sqlite3") as db:
        db.create_missed_post_request(
            "request1",
            "https://x.com/thsottiaux/status/200",
            "123",
            "2999-01-01T00:00:00+00:00",
        )
        client = FakeTelegramClient(
            [
                {"ok": True, "result": True},
                {"ok": True, "result": {"message_id": 1}},
                httpx.ReadTimeout("timeout"),
                httpx.ReadTimeout("timeout"),
                httpx.ReadTimeout("timeout"),
            ]
        )
        consumer = TelegramFeedbackConsumer(settings, db, client=client, missed_recovery=recovery)

        with pytest.raises(NotificationError, match="failed after 3 attempts"):
            await consumer._handle_missed_rating("callback", "request1", 8)

        request = db.get_missed_post_request("request1")
        assert request["status"] == "pending"
        assert "confirmation delivery" in request["last_error"]
