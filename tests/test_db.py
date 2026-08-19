from pathlib import Path

from xlistener.db import SQLiteState
from xlistener.models import Tweet


def test_processed_ids_are_separate_from_durable_tweets(tmp_path: Path) -> None:
    tweet = Tweet(id="1", author_handle="thsottiaux", text="ignored", url="https://x.com/thsottiaux/status/1", source="test")
    with SQLiteState(tmp_path / "state.sqlite3") as db:
        db.record_processed_id(tweet.id, "ignored")
        assert db.was_recently_processed(tweet.id)
        assert db.connection.execute("SELECT COUNT(*) FROM tweets").fetchone()[0] == 0

        db.retain_tweet(tweet, "notification")
        assert db.connection.execute("SELECT COUNT(*) FROM tweets").fetchone()[0] == 1


def test_feedback_updates_without_duplication(tmp_path: Path) -> None:
    tweet = Tweet(id="1", author_handle="thsottiaux", text="retained", url="https://x.com/thsottiaux/status/1", source="test")
    with SQLiteState(tmp_path / "state.sqlite3") as db:
        db.retain_tweet(tweet, "notification")
        db.save_feedback(tweet.id, 3, telegram_update_id="10")
        db.save_feedback(tweet.id, 9, telegram_update_id="11")

        rows = db.connection.execute("SELECT rating, telegram_update_id FROM feedback").fetchall()
        assert [(row["rating"], row["telegram_update_id"]) for row in rows] == [(9, "11")]
