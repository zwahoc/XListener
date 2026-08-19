from xlistener.config import load_settings
from xlistener.db import SQLiteState
from xlistener.learning import learned_prompt_context, refresh_learning_profile
from xlistener.models import ClassificationResult, Tweet


def _seed(db: SQLiteState, tweet_id: str, tags: list[str], rating: int) -> None:
    tweet = Tweet(
        id=tweet_id,
        author_handle="thsottiaux",
        text=f"Post {tweet_id}",
        url=f"https://x.com/thsottiaux/status/{tweet_id}",
        source="test",
    )
    result = ClassificationResult(
        relevant=True,
        importance=8,
        topic="codex",
        tags=tags,
        reason="Useful reason.",
        summary="Useful summary.",
    )
    db.retain_tweet(tweet, "notification")
    db.save_analysis(tweet_id, result, "qwen3:4b")
    db.save_feedback(tweet_id, rating)


def test_refresh_learning_profile_recomputes_tag_scores(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    with SQLiteState(tmp_path / "state.sqlite3") as db:
        _seed(db, "1", ["reset", "codex"], 10)
        _seed(db, "2", ["reset"], 1)
        profile = refresh_learning_profile(db, settings)

        reset = next(item for item in profile["tags"] if item["tag"] == "reset")
        assert reset["sample_count"] == 2
        assert reset["score"] == 0.0
        assert db.connection.execute("SELECT COUNT(*) FROM learned_profile_versions").fetchone()[0] == 1


def test_learned_prompt_context_contains_affinity_and_examples(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    with SQLiteState(tmp_path / "state.sqlite3") as db:
        _seed(db, "1", ["release"], 9)
        refresh_learning_profile(db, settings)
        context = learned_prompt_context(db, settings)

        assert "release" in context
        assert "+0.78" in context
        assert "rating=9/10" in context


def test_learned_prompt_context_backfills_missing_profile(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    with SQLiteState(tmp_path / "state.sqlite3") as db:
        _seed(db, "1", ["codex"], 10)

        assert db.connection.execute("SELECT COUNT(*) FROM tag_affinity").fetchone()[0] == 0
        context = learned_prompt_context(db, settings)

        assert "codex: +1.00" in context
        assert db.connection.execute("SELECT COUNT(*) FROM learned_profile_versions").fetchone()[0] == 1


def test_learned_prompt_context_balances_positive_and_negative_examples(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    settings.learning.max_examples_in_prompt = 2
    with SQLiteState(tmp_path / "state.sqlite3") as db:
        _seed(db, "1", ["release"], 10)
        _seed(db, "2", ["marketing"], 1)
        refresh_learning_profile(db, settings)

        context = learned_prompt_context(db, settings)

        assert "rating=10/10" in context
        assert "rating=1/10" in context
