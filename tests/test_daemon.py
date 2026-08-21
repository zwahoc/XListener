import asyncio
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


async def test_daemon_processes_late_visible_post_older_than_cursor(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.database_path = tmp_path / "state.sqlite3"
    late_reply = make_tweet("499").model_copy(update={"is_reply": True})
    newest = make_tweet("501")
    classifier = FakeClassifier(result())
    notifier = FakeNotifier()

    with SQLiteState(settings.runtime.database_path) as db:
        db.set_cursor("500")
        outcome = await TextDaemon(
            settings,
            db,
            FakeFetcher([late_reply, newest]),
            notifier,
            classifier=classifier,
        ).poll_once()

        assert outcome.queued == 2
        assert outcome.processed == 2
        assert notifier.sent == ["499", "501"]
        assert db.get_cursor() == "501"


async def test_discovery_queue_survives_before_processing(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.database_path = tmp_path / "state.sqlite3"
    settings.fetcher.bootstrap_mode = "process_all"
    tweets = [make_tweet("600"), make_tweet("601"), make_tweet("602")]
    notifier = FakeNotifier()

    with SQLiteState(settings.runtime.database_path) as db:
        first_daemon = TextDaemon(
            settings,
            db,
            FakeFetcher(tweets),
            notifier,
            classifier=FakeClassifier(result()),
        )
        discovered = await first_daemon.discover_once()

        assert discovered.queued == 3
        assert db.queued_count() == 3

        restarted_daemon = TextDaemon(
            settings,
            db,
            FakeFetcher([]),
            notifier,
            classifier=FakeClassifier(result()),
        )
        consumed = await restarted_daemon.process_queue_once(limit=10)

        assert consumed.processed == 3
        assert notifier.sent == ["600", "601", "602"]
        assert db.queued_count() == 0


async def test_discovery_continues_while_llm_is_processing(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.runtime.database_path = tmp_path / "state.sqlite3"
    settings.fetcher.bootstrap_mode = "process_all"
    fetcher = FakeFetcher([make_tweet("700")])
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingClassifier(FakeClassifier):
        async def classify(self, tweet, recent_summaries=(), learned_context="", verify=False):
            self.calls += 1
            started.set()
            await release.wait()
            return self.result, json.dumps(self.result.model_dump())

    with SQLiteState(settings.runtime.database_path) as db:
        daemon = TextDaemon(
            settings,
            db,
            fetcher,
            FakeNotifier(),
            classifier=BlockingClassifier(result()),
        )
        await daemon.discover_once()
        processing = asyncio.create_task(daemon.process_queue_once(limit=1))
        await started.wait()

        fetcher.tweets.append(make_tweet("701"))
        discovered = await daemon.discover_once()

        assert discovered.queued == 1
        assert db.get_tweet("701") is not None
        release.set()
        await processing


def test_instance_lock_rejects_second_owner(tmp_path) -> None:
    lock_path = tmp_path / "xlistener.lock"
    with InstanceLock(lock_path):
        with pytest.raises(InstanceAlreadyRunning):
            with InstanceLock(lock_path):
                pass
