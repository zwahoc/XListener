import json
from datetime import datetime, timezone

from xlistener.classifier import ClassificationTrace
from xlistener.config import load_settings
import pytest

from xlistener.daemon import InstanceAlreadyRunning, InstanceLock, TextDaemon
from xlistener.db import SQLiteState
from xlistener.models import ClassificationResult, RelatedPost, Tweet


def make_tweet(tweet_id: str, text: str = "New Codex release") -> Tweet:
    return Tweet(
        id=tweet_id,
        author_handle="thsottiaux",
        text=text,
        url=f"https://x.com/thsottiaux/status/{tweet_id}",
        created_at=datetime.now(timezone.utc),
        source="test",
    )


class FakeFetcher:
    def __init__(self, tweets: list[Tweet]):
        self.tweets = tweets
        self.enriched: list[str] = []

    async def fetch_recent(self, limit=20):
        return self.tweets[-limit:]

    async def enrich_context(self, tweet):
        self.enriched.append(tweet.id)
        return tweet.model_copy(
            update={
                "related_posts": [
                    RelatedPost(
                        relationship="quoted",
                        id="90",
                        author_handle="openai",
                        text="Supporting context",
                        url="https://x.com/openai/status/90",
                    )
                ]
            }
        )


class FakeClassifier:
    def __init__(self, result: ClassificationResult):
        self.result = result
        self.calls = 0
        self.last_trace = ClassificationTrace()

    async def classify(self, tweet, recent_summaries=(), learned_context="", verify=False):
        self.calls += 1
        return self.result, json.dumps(self.result.model_dump())


class FakeNotifier:
    def __init__(self, failures=0):
        self.failures = failures
        self.sent: list[str] = []

    async def send(self, tweet, result):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("Telegram unavailable")
        self.sent.append(tweet.id)
        return f"message-{tweet.id}"


def result(relevant=True, importance=8) -> ClassificationResult:
    return ClassificationResult(
        relevant=relevant,
        importance=importance,
        topic="codex release" if relevant else "conversation",
        tags=["codex_release" if relevant else "conversation"],
        tone="literal",
        stance="neutral",
        reason="Useful product information." if relevant else "No useful product information.",
        summary="A product update." if relevant else "Routine conversation.",
    )


async def test_daemon_baselines_existing_posts_without_processing(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.database_path = tmp_path / "state.sqlite3"
    fetcher = FakeFetcher([make_tweet("100"), make_tweet("101")])
    classifier = FakeClassifier(result())
    notifier = FakeNotifier()

    with SQLiteState(settings.runtime.database_path) as db:
        outcome = await TextDaemon(settings, db, fetcher, notifier, classifier=classifier).poll_once()

        assert outcome.baseline_initialized is True
        assert db.get_cursor() == "101"
        assert classifier.calls == 0
        assert notifier.sent == []


async def test_daemon_discards_ignored_content_and_advances_cursor(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.database_path = tmp_path / "state.sqlite3"
    settings.fetcher.bootstrap_mode = "process_latest"
    tweet = make_tweet("200", "A joke")

    with SQLiteState(settings.runtime.database_path) as db:
        outcome = await TextDaemon(
            settings,
            db,
            FakeFetcher([tweet]),
            FakeNotifier(),
            classifier=FakeClassifier(result(False, 2)),
        ).poll_once()

        assert outcome.ignored == 1
        assert db.get_cursor() == "200"
        assert db.connection.execute("SELECT COUNT(*) FROM tweets").fetchone()[0] == 0
        checkpoint = db.connection.execute("SELECT outcome FROM processed_ids WHERE tweet_id = '200'").fetchone()
        assert checkpoint["outcome"] == "ignored"


async def test_notification_retry_reuses_saved_analysis(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.database_path = tmp_path / "state.sqlite3"
    settings.fetcher.bootstrap_mode = "process_latest"
    settings.runtime.retry_base_seconds = 1
    tweet = make_tweet("300")
    fetcher = FakeFetcher([tweet])
    classifier = FakeClassifier(result())
    notifier = FakeNotifier(failures=1)

    with SQLiteState(settings.runtime.database_path) as db:
        daemon = TextDaemon(settings, db, fetcher, notifier, classifier=classifier)
        first = await daemon.poll_once()
        assert first.failed == 1
        assert classifier.calls == 1
        row = db.connection.execute("SELECT status, failure_stage FROM tweets WHERE id = '300'").fetchone()
        assert (row["status"], row["failure_stage"]) == ("failed", "notification")

        db.connection.execute("UPDATE tweets SET next_retry_at = '2000-01-01T00:00:00+00:00' WHERE id = '300'")
        db.connection.commit()
        second = await daemon.poll_once()

        assert second.retried == 1
        assert classifier.calls == 1
        assert notifier.sent == ["300"]
        assert db.connection.execute("SELECT status FROM tweets WHERE id = '300'").fetchone()["status"] == "notified"


async def test_daemon_retains_enriched_context_for_classification_failure(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.database_path = tmp_path / "state.sqlite3"
    settings.fetcher.bootstrap_mode = "process_latest"
    tweet = make_tweet("400")

    class FailingClassifier(FakeClassifier):
        async def classify(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError("Ollama unavailable")

    with SQLiteState(settings.runtime.database_path) as db:
        outcome = await TextDaemon(
            settings,
            db,
            FakeFetcher([tweet]),
            FakeNotifier(),
            classifier=FailingClassifier(result()),
        ).poll_once()

        assert outcome.failed == 1
        retained = db.get_tweet("400")
        assert retained is not None
        assert retained.related_posts[0].text == "Supporting context"
        assert db.get_cursor() == "400"


async def test_daemon_does_not_move_cursor_backward(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.database_path = tmp_path / "state.sqlite3"

    with SQLiteState(settings.runtime.database_path) as db:
        db.set_cursor("500")
        await TextDaemon(
            settings,
            db,
            FakeFetcher([make_tweet("499")]),
            FakeNotifier(),
            classifier=FakeClassifier(result()),
        ).poll_once()

        assert db.get_cursor() == "500"


def test_instance_lock_rejects_second_owner(tmp_path) -> None:
    lock_path = tmp_path / "xlistener.lock"
    with InstanceLock(lock_path):
        with pytest.raises(InstanceAlreadyRunning):
            with InstanceLock(lock_path):
                pass
