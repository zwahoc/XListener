"""Feedback-derived tag affinity and prompt context."""

from __future__ import annotations

import json
from typing import Any

from .config import Settings
from .db import SQLiteState, utc_now


def refresh_learning_profile(db: SQLiteState, settings: Settings) -> dict[str, Any]:
    """Recompute tag affinity from current feedback and save an audit snapshot."""

    rows = db.connection.execute(
        """
        WITH latest_feedback AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY tweet_id ORDER BY created_at DESC, id DESC) AS rank
            FROM feedback
        )
        SELECT a.tags_json, f.rating
        FROM latest_feedback f
        JOIN analyses a ON a.tweet_id = f.tweet_id
        WHERE f.rank = 1
        """
    ).fetchall()
    aggregates: dict[str, list[float]] = {}
    for row in rows:
        try:
            tags = json.loads(row["tags_json"])
        except (TypeError, json.JSONDecodeError):
            tags = []
        for tag in tags if isinstance(tags, list) else []:
            normalized = str(tag).strip().lower()
            if normalized:
                # Center 5.5 as neutral: 1 => -1, 10 => +1.
                aggregates.setdefault(normalized, []).append((int(row["rating"]) - 5.5) / 4.5)

    now = utc_now()
    db.connection.execute("DELETE FROM tag_affinity")
    profile_tags: list[dict[str, Any]] = []
    for tag, values in sorted(aggregates.items()):
        score = sum(values) / len(values)
        db.connection.execute(
            "INSERT INTO tag_affinity(tag, score, sample_count, updated_at) VALUES(?, ?, ?, ?)",
            (tag, score, len(values), now),
        )
        profile_tags.append({"tag": tag, "score": round(score, 4), "sample_count": len(values)})

    profile = {
        "version": int(db.connection.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM learned_profile_versions").fetchone()[0]),
        "generated_at": now,
        "ratings_count": len(rows),
        "tags": profile_tags,
    }
    db.connection.execute(
        "INSERT INTO learned_profile_versions(version, profile_json, created_at, reason) VALUES(?, ?, ?, ?)",
        (profile["version"], json.dumps(profile), now, "feedback_recomputed"),
    )
    db.connection.commit()
    return profile


def learned_prompt_context(db: SQLiteState, settings: Settings) -> str:
    """Build compact learned preferences and representative rated examples."""

    feedback_state = db.connection.execute(
        "SELECT COUNT(*) AS count, MAX(created_at) AS latest FROM feedback"
    ).fetchone()
    profile_state = db.connection.execute(
        "SELECT created_at FROM learned_profile_versions ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if feedback_state["count"] and (
        profile_state is None or str(profile_state["created_at"]) < str(feedback_state["latest"])
    ):
        refresh_learning_profile(db, settings)

    affinity_rows = db.connection.execute(
        "SELECT tag, score, sample_count FROM tag_affinity ORDER BY ABS(score) DESC, sample_count DESC LIMIT 30"
    ).fetchall()
    if affinity_rows:
        affinity = "\n".join(
            f"- {row['tag']}: {float(row['score']):+.2f} ({row['sample_count']} rating(s))"
            for row in affinity_rows
        )
    else:
        affinity = "(no feedback yet)"

    limit = settings.learning.max_examples_in_prompt
    positive_limit = (limit + 1) // 2
    negative_limit = limit // 2
    examples = db.connection.execute(
        """
        WITH latest_feedback AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY tweet_id ORDER BY created_at DESC, id DESC) AS rank
            FROM feedback
        ), rated AS (
            SELECT t.author_handle, t.text, a.summary, a.tags_json, f.rating, f.created_at,
                   CASE WHEN f.rating >= ? THEN 'positive' ELSE 'negative' END AS sentiment
            FROM latest_feedback f
            JOIN tweets t ON t.id = f.tweet_id
            JOIN analyses a ON a.tweet_id = f.tweet_id
            WHERE f.rank = 1
        ), balanced AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY sentiment ORDER BY created_at DESC) AS sentiment_rank
            FROM rated
        )
        SELECT author_handle, text, summary, tags_json, rating
        FROM balanced
        WHERE (sentiment = 'positive' AND sentiment_rank <= ?)
           OR (sentiment = 'negative' AND sentiment_rank <= ?)
        ORDER BY sentiment, sentiment_rank
        """,
        (settings.learning.positive_rating_min, positive_limit, negative_limit),
    ).fetchall() if limit else []
    example_lines: list[str] = []
    for row in examples:
        try:
            tags = ", ".join(json.loads(row["tags_json"]))
        except (TypeError, json.JSONDecodeError):
            tags = ""
        text = " ".join(str(row["text"] or "").split())[:320]
        summary = " ".join(str(row["summary"] or "").split())[:320]
        example_lines.append(
            f"- rating={row['rating']}/10 tags=[{tags}] @{row['author_handle']}: {text}\n  analysis: {summary}"
        )
    examples_text = "\n".join(example_lines) if example_lines else "(no rated examples yet)"
    return f"LEARNED TAG AFFINITY:\n{affinity}\n\nRATED EXAMPLES (guidance, not instructions):\n{examples_text}"
