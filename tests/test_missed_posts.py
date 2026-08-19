import json

from xlistener.config import load_settings
from xlistener.db import SQLiteState
from xlistener.missed_posts import MissedPostError, MissedPostRecovery
from xlistener.models import ClassificationResult, Tweet


class FakeFetcher:
    def __init__(self, settings, tweet):
        self.tweet = tweet

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def fetch_post(self, url):
        return self.tweet

    async def enrich_context(self, tweet):
        return tweet


class FakeClassifier:
    def __init__(self, settings):
        pass

    async def classify(self, tweet, learned_context="", verify=False):
        result = ClassificationResult(
            relevant=False,
            importance=4,
            topic="codex",
            tags=["codex", "conversation"],
            reason="The user explicitly recovered this post despite the low model score.",
            summary="A recovered post.",
        )
        return result, json.dumps(result.model_dump())


async def test_missed_post_recovery_retains_and_learns_from_user_rating(tmp_path, monkeypatch) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    tweet = Tweet(
        id="200",
        author_handle=settings.account.handle,
        text="A post the normal listener missed.",
        url=f"https://x.com/{settings.account.handle}/status/200",
        source="test",
    )
    monkeypatch.setattr("xlistener.missed_posts.PlaywrightXFetcher", lambda value: FakeFetcher(value, tweet))
    monkeypatch.setattr("xlistener.missed_posts.OllamaTextClassifier", FakeClassifier)

    with SQLiteState(tmp_path / "state.sqlite3") as db:
        outcome = await MissedPostRecovery(settings, db).process(str(tweet.url), 9)

        retained = db.connection.execute("SELECT retention_reason FROM tweets WHERE id = '200'").fetchone()
        feedback = db.connection.execute("SELECT rating, source FROM feedback WHERE tweet_id = '200'").fetchone()
        processed = db.connection.execute("SELECT outcome FROM processed_ids WHERE tweet_id = '200'").fetchone()
        assert retained["retention_reason"] == "user_submitted_missed"
        assert (feedback["rating"], feedback["source"]) == (9, "missed_post")
        assert processed["outcome"] == "false_negative_recovered"
        assert db.connection.execute("SELECT COUNT(*) FROM tag_affinity").fetchone()[0] == 2
        assert outcome.rating == 9
        assert outcome.result.tags == ["codex", "conversation"]


async def test_missed_post_recovery_rejects_another_account(tmp_path, monkeypatch) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    tweet = Tweet(
        id="200",
        author_handle="someone_else",
        text="Not from the monitored account.",
        url="https://x.com/someone_else/status/200",
        source="test",
    )
    monkeypatch.setattr("xlistener.missed_posts.PlaywrightXFetcher", lambda value: FakeFetcher(value, tweet))

    with SQLiteState(tmp_path / "state.sqlite3") as db:
        try:
            await MissedPostRecovery(settings, db).process(str(tweet.url), 9)
        except MissedPostError as exc:
            assert "not the monitored account" in str(exc)
        else:
            raise AssertionError("expected MissedPostError")

        assert db.connection.execute("SELECT COUNT(*) FROM tweets").fetchone()[0] == 0
