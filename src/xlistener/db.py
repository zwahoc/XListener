"""SQLite state store for cursors, deduplication, and durable work."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import ClassificationResult, Tweet


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteState:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.initialize()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS processed_ids (
                tweet_id TEXT PRIMARY KEY,
                first_seen_at TEXT NOT NULL,
                outcome TEXT NOT NULL,
                expires_at TEXT
            );
            CREATE TABLE IF NOT EXISTS tweets (
                id TEXT PRIMARY KEY,
                author_handle TEXT NOT NULL,
                text TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TEXT,
                is_reply INTEGER NOT NULL DEFAULT 0,
                in_reply_to_url TEXT,
                media_json TEXT NOT NULL,
                is_repost INTEGER NOT NULL DEFAULT 0,
                related_posts_json TEXT NOT NULL,
                context_complete INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                retention_reason TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                processed_at TEXT,
                last_error TEXT,
                failure_stage TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                next_retry_at TEXT
            );
            CREATE TABLE IF NOT EXISTS analyses (
                tweet_id TEXT PRIMARY KEY REFERENCES tweets(id),
                relevant INTEGER NOT NULL,
                importance INTEGER NOT NULL,
                topic TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                tone TEXT NOT NULL DEFAULT 'uncertain',
                stance TEXT NOT NULL DEFAULT 'uncertain',
                reason TEXT NOT NULL,
                summary TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                raw_response TEXT
            );
            CREATE TABLE IF NOT EXISTS notifications (
                tweet_id TEXT PRIMARY KEY REFERENCES tweets(id),
                provider TEXT NOT NULL,
                provider_message_id TEXT,
                sent_at TEXT NOT NULL,
                last_error TEXT
            );
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT NOT NULL REFERENCES tweets(id),
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 10),
                source TEXT NOT NULL,
                telegram_update_id TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tag_affinity (
                tag TEXT PRIMARY KEY,
                score REAL NOT NULL DEFAULT 0,
                sample_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS learned_profile_versions (
                version INTEGER PRIMARY KEY,
                profile_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reason TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS telegram_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_missed_posts (
                request_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                completed_at TEXT,
                last_error TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_tweet_source
            ON feedback(tweet_id, source);
            """
        )
        analysis_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(analyses)").fetchall()
        }
        if "tone" not in analysis_columns:
            self.connection.execute("ALTER TABLE analyses ADD COLUMN tone TEXT NOT NULL DEFAULT 'uncertain'")
        if "stance" not in analysis_columns:
            self.connection.execute("ALTER TABLE analyses ADD COLUMN stance TEXT NOT NULL DEFAULT 'uncertain'")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteState":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def get_state(self, key: str) -> str | None:
        row = self.connection.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_state(self, key: str, value: str) -> None:
        self.connection.execute(
            "INSERT INTO app_state(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.connection.commit()

    def get_cursor(self) -> str | None:
        return self.get_state("last_seen_id")

    def set_cursor(self, tweet_id: str) -> None:
        self.set_state("last_seen_id", tweet_id)

    def was_recently_processed(self, tweet_id: str) -> bool:
        row = self.connection.execute("SELECT 1 FROM processed_ids WHERE tweet_id = ?", (tweet_id,)).fetchone()
        return row is not None

    def record_processed_id(self, tweet_id: str, outcome: str, retention_days: int = 30) -> None:
        expires = (datetime.now(timezone.utc) + timedelta(days=retention_days)).isoformat()
        self.connection.execute(
            """
            INSERT INTO processed_ids(tweet_id, first_seen_at, outcome, expires_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(tweet_id) DO UPDATE SET outcome=excluded.outcome, expires_at=excluded.expires_at
            """,
            (tweet_id, utc_now(), outcome, expires),
        )
        self.connection.commit()

    def prune_processed_ids(self, max_rows: int = 2000) -> None:
        self.connection.execute("DELETE FROM processed_ids WHERE expires_at < ?", (utc_now(),))
        self.connection.execute(
            """
            DELETE FROM processed_ids
            WHERE tweet_id IN (
                SELECT tweet_id FROM processed_ids ORDER BY first_seen_at DESC LIMIT -1 OFFSET ?
            )
            """,
            (max_rows,),
        )
        self.connection.commit()

    def retain_tweet(self, tweet: Tweet, retention_reason: str, status: str = "discovered") -> None:
        self.connection.execute(
            """
            INSERT INTO tweets(
                id, author_handle, text, url, created_at, is_reply, in_reply_to_url,
                media_json, is_repost, related_posts_json, context_complete, source,
                status, retention_reason, first_seen_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                tweet.id,
                tweet.author_handle,
                tweet.text,
                str(tweet.url),
                tweet.created_at.isoformat() if tweet.created_at else None,
                int(tweet.is_reply),
                str(tweet.in_reply_to_url) if tweet.in_reply_to_url else None,
                json.dumps([item.model_dump(mode="json") for item in tweet.media]),
                int(tweet.is_repost),
                json.dumps([item.model_dump(mode="json") for item in tweet.related_posts]),
                int(tweet.context_complete),
                tweet.source,
                status,
                retention_reason,
                utc_now(),
            ),
        )
        self.connection.commit()

    def save_analysis(self, tweet_id: str, result: ClassificationResult, model: str, raw_response: str | None = None) -> None:
        self.connection.execute(
            """
            INSERT INTO analyses(
                tweet_id, relevant, importance, topic, tags_json, tone, stance,
                reason, summary, model, created_at, raw_response
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tweet_id) DO UPDATE SET
                relevant=excluded.relevant, importance=excluded.importance, topic=excluded.topic,
                tags_json=excluded.tags_json, tone=excluded.tone, stance=excluded.stance,
                reason=excluded.reason, summary=excluded.summary,
                model=excluded.model, created_at=excluded.created_at, raw_response=excluded.raw_response
            """,
            (
                tweet_id,
                int(result.relevant),
                result.importance,
                result.topic,
                json.dumps(result.tags),
                result.tone,
                result.stance,
                result.reason,
                result.summary,
                model,
                utc_now(),
                raw_response,
            ),
        )
        self.connection.execute("UPDATE tweets SET status = 'classified', processed_at = ? WHERE id = ?", (utc_now(), tweet_id))
        self.connection.commit()

    def record_notification(self, tweet_id: str, provider_message_id: str, provider: str = "telegram") -> None:
        self.connection.execute(
            """
            INSERT INTO notifications(tweet_id, provider, provider_message_id, sent_at, last_error)
            VALUES(?, ?, ?, ?, NULL)
            ON CONFLICT(tweet_id) DO UPDATE SET
                provider=excluded.provider,
                provider_message_id=excluded.provider_message_id,
                sent_at=excluded.sent_at,
                last_error=NULL
            """,
            (tweet_id, provider, provider_message_id, utc_now()),
        )
        self.connection.execute("UPDATE tweets SET status = 'notified', processed_at = ? WHERE id = ?", (utc_now(), tweet_id))
        self.connection.commit()

    def save_feedback(
        self,
        tweet_id: str,
        rating: int,
        source: str = "telegram_inline",
        telegram_update_id: str | None = None,
    ) -> None:
        if not 1 <= rating <= 10:
            raise ValueError("rating must be between 1 and 10")
        self.connection.execute(
            """
            INSERT INTO feedback(tweet_id, rating, source, telegram_update_id, created_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(tweet_id, source) DO UPDATE SET
                rating=excluded.rating,
                telegram_update_id=excluded.telegram_update_id,
                created_at=excluded.created_at
            """,
            (tweet_id, rating, source, telegram_update_id, utc_now()),
        )
        self.connection.commit()

    def get_telegram_offset(self) -> int:
        row = self.connection.execute("SELECT value FROM telegram_state WHERE key = 'update_offset'").fetchone()
        return int(row["value"]) if row else 0

    def set_telegram_offset(self, offset: int) -> None:
        self.connection.execute(
            """
            INSERT INTO telegram_state(key, value) VALUES('update_offset', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (str(offset),),
        )
        self.connection.commit()

    def create_missed_post_request(self, request_id: str, url: str, chat_id: str, expires_at: str) -> None:
        self.connection.execute(
            """
            INSERT INTO pending_missed_posts(request_id, url, chat_id, status, created_at, expires_at)
            VALUES(?, ?, ?, 'pending', ?, ?)
            """,
            (request_id, url, chat_id, utc_now(), expires_at),
        )
        self.connection.commit()

    def get_missed_post_request(self, request_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM pending_missed_posts WHERE request_id = ?", (request_id,)
        ).fetchone()

    def complete_missed_post_request(self, request_id: str) -> None:
        self.connection.execute(
            "UPDATE pending_missed_posts SET status = 'completed', completed_at = ?, last_error = NULL WHERE request_id = ?",
            (utc_now(), request_id),
        )
        self.connection.commit()

    def fail_missed_post_request(self, request_id: str, error: str) -> None:
        self.connection.execute(
            "UPDATE pending_missed_posts SET status = 'pending', last_error = ? WHERE request_id = ?",
            (error[:500], request_id),
        )
        self.connection.commit()

    def prune_missed_post_requests(self) -> None:
        self.connection.execute(
            "DELETE FROM pending_missed_posts WHERE expires_at < ? AND status = 'pending'", (utc_now(),)
        )
        self.connection.commit()
