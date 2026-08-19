"""Continuous text polling, classification, delivery, and feedback orchestration."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from .classifier import OllamaTextClassifier
from .config import Settings
from .db import SQLiteState
from .fetchers.playwright_x import PlaywrightXFetcher, XAuthenticationRequired
from .learning import learned_prompt_context
from .missed_posts import MissedPostRecovery
from .models import ClassificationResult, Tweet
from .notification import TelegramFeedbackConsumer, TelegramNotifier, should_notify


LOG = logging.getLogger(__name__)
Sleep = Callable[[float], Awaitable[None]]


class DaemonFetcher(Protocol):
    async def fetch_recent(self, limit: int = 20) -> list[Tweet]: ...
    async def enrich_context(self, tweet: Tweet) -> Tweet: ...


class DaemonNotifier(Protocol):
    async def send(self, tweet: Tweet, result: ClassificationResult) -> str: ...


@dataclass(frozen=True)
class PollResult:
    fetched: int = 0
    processed: int = 0
    notified: int = 0
    ignored: int = 0
    failed: int = 0
    retried: int = 0
    baseline_initialized: bool = False


class InstanceAlreadyRunning(RuntimeError):
    """Raised when another XListener daemon owns the runtime lock."""


class InstanceLock:
    def __init__(self, path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.handle = self.path.open("a+b")
            self.handle.seek(0)
            if self.handle.read(1) == b"":
                self.handle.write(b"0")
                self.handle.flush()
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if self.handle is not None:
                self.handle.close()
            self.handle = None
            raise InstanceAlreadyRunning("Another XListener daemon is already running") from exc
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.handle is None:
            return
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None


def _tweet_order(tweet: Tweet) -> tuple[float, int, str]:
    created = tweet.created_at.timestamp() if tweet.created_at else 0.0
    try:
        numeric_id = int(tweet.id)
    except ValueError:
        numeric_id = 0
    return created, numeric_id, tweet.id


def _is_newer(tweet_id: str, cursor: str) -> bool:
    try:
        return int(tweet_id) > int(cursor)
    except ValueError:
        return tweet_id != cursor


class TextDaemon:
    def __init__(
        self,
        settings: Settings,
        state: SQLiteState,
        fetcher: DaemonFetcher,
        notifier: DaemonNotifier,
        classifier: OllamaTextClassifier | None = None,
        sleep: Sleep = asyncio.sleep,
        rng: random.Random | None = None,
    ):
        self.settings = settings
        self.state = state
        self.fetcher = fetcher
        self.notifier = notifier
        self.classifier = classifier or OllamaTextClassifier(settings)
        self.sleep = sleep
        self.rng = rng or random.Random()
        self.work_lock = asyncio.Lock()

    def _retry_delay(self, tweet_id: str) -> int:
        attempts = self.state.get_attempt_count(tweet_id)
        return min(
            self.settings.runtime.retry_max_seconds,
            self.settings.runtime.retry_base_seconds * (2 ** min(attempts, 6)),
        )

    def _mark_failure(self, tweet: Tweet, stage: str, exc: Exception) -> None:
        self.state.retain_tweet(tweet, "retry", status="failed")
        self.state.update_tweet_payload(tweet)
        self.state.mark_failure(
            tweet.id,
            stage,
            str(exc),
            retry_delay_seconds=self._retry_delay(tweet.id),
            retention_days=self.settings.learning.processed_id_retention_days,
        )
        LOG.warning("Post %s failed during %s: %s", tweet.id, stage, exc)

    async def _classify(self, tweet: Tweet) -> tuple[ClassificationResult, str]:
        learned_context = learned_prompt_context(self.state, self.settings)
        return await self.classifier.classify(
            tweet,
            recent_summaries=self.state.recent_notification_summaries(limit=5),
            learned_context=learned_context,
            verify=True,
        )

    async def _deliver_saved_analysis(self, tweet: Tweet, result: ClassificationResult) -> bool:
        try:
            message_id = await self.notifier.send(tweet, result)
        except Exception as exc:
            self._mark_failure(tweet, "notification", exc)
            return False
        self.state.record_notification(tweet.id, message_id)
        self.state.record_processed_id(
            tweet.id,
            "notified",
            retention_days=self.settings.learning.processed_id_retention_days,
        )
        LOG.info("Notified post %s as Telegram message %s", tweet.id, message_id)
        return True

    async def process_tweet(self, tweet: Tweet, retry: bool = False) -> str:
        existing_analysis = self.state.get_analysis(tweet.id)
        if existing_analysis is not None:
            if should_notify(existing_analysis, self.settings):
                return "notified" if await self._deliver_saved_analysis(tweet, existing_analysis) else "failed"
            self.state.record_processed_id(
                tweet.id,
                "ignored",
                retention_days=self.settings.learning.processed_id_retention_days,
            )
            self.state.discard_tweet(tweet.id)
            return "ignored"

        working_tweet = tweet
        try:
            working_tweet = await self.fetcher.enrich_context(tweet)
            result, raw_response = await self._classify(working_tweet)
        except Exception as exc:
            self._mark_failure(working_tweet, "classification", exc)
            return "failed"

        if not should_notify(result, self.settings):
            self.state.record_processed_id(
                working_tweet.id,
                "ignored",
                retention_days=self.settings.learning.processed_id_retention_days,
            )
            self.state.discard_tweet(working_tweet.id)
            LOG.info("Ignored post %s at importance %s", working_tweet.id, result.importance)
            return "ignored"

        self.state.retain_tweet(working_tweet, "notification", status="classified")
        self.state.update_tweet_payload(working_tweet)
        self.state.save_analysis(working_tweet.id, result, self.settings.llm.model, raw_response)
        return "notified" if await self._deliver_saved_analysis(working_tweet, result) else "failed"

    async def retry_due(self) -> int:
        retried = 0
        for tweet in self.state.list_retry_tweets(limit=self.settings.fetcher.max_posts_per_poll):
            await self.process_tweet(tweet, retry=True)
            retried += 1
        return retried

    async def poll_once(self) -> PollResult:
        async with self.work_lock:
            retried = await self.retry_due()
            tweets = sorted(
                await self.fetcher.fetch_recent(self.settings.fetcher.max_posts_per_poll),
                key=_tweet_order,
            )
            if not tweets:
                return PollResult(retried=retried)

            cursor = self.state.get_cursor()
            if cursor is None and self.settings.fetcher.bootstrap_mode == "baseline":
                self.state.set_cursor(tweets[-1].id)
                self.state.prune_processed_ids(self.settings.learning.processed_id_max_rows)
                LOG.info("Initialized baseline cursor at post %s", tweets[-1].id)
                return PollResult(fetched=len(tweets), retried=retried, baseline_initialized=True)

            if cursor is None and self.settings.fetcher.bootstrap_mode == "process_latest":
                candidates = [tweets[-1]]
            elif cursor is None:
                candidates = tweets
            else:
                candidates = [tweet for tweet in tweets if _is_newer(tweet.id, cursor)]
            candidates = [
                tweet
                for tweet in candidates
                if (self.settings.fetcher.include_replies or not tweet.is_reply)
                and (self.settings.fetcher.include_reposts or not tweet.is_repost)
            ]

            processed = notified = ignored = failed = 0
            for tweet in candidates:
                if self.state.was_recently_processed(tweet.id):
                    continue
                outcome = await self.process_tweet(tweet)
                processed += 1
                notified += int(outcome == "notified")
                ignored += int(outcome == "ignored")
                failed += int(outcome == "failed")

            if cursor is None or _is_newer(tweets[-1].id, cursor):
                self.state.set_cursor(tweets[-1].id)
            self.state.prune_processed_ids(self.settings.learning.processed_id_max_rows)
            return PollResult(
                fetched=len(tweets),
                processed=processed,
                notified=notified,
                ignored=ignored,
                failed=failed,
                retried=retried,
            )

    async def polling_loop(self, stop_event: asyncio.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            delay = self.rng.uniform(
                self.settings.fetcher.poll_min_seconds,
                self.settings.fetcher.poll_max_seconds,
            )
            try:
                result = await self.poll_once()
                LOG.info("Poll complete: %s", result)
            except XAuthenticationRequired as exc:
                LOG.error("X authentication requires attention: %s", exc)
                delay = self.settings.runtime.auth_error_seconds
            except Exception:
                LOG.exception("X polling failed")
                delay = self.settings.runtime.poll_error_seconds
            LOG.info("Next X poll in %.1f seconds", delay)
            if stop_event is None:
                await self.sleep(delay)
            else:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass


async def _watch_stop_request(path, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        if path.exists():
            stop_event.set()
            return
        await asyncio.sleep(1)


async def run_daemon(settings: Settings, once: bool = False) -> PollResult | None:
    with InstanceLock(settings.runtime.instance_lock_path):
        with SQLiteState(settings.runtime.database_path) as state:
            async with PlaywrightXFetcher(settings) as fetcher, TelegramNotifier(settings) as notifier:
                daemon = TextDaemon(settings, state, fetcher, notifier)
                if once:
                    return await daemon.poll_once()

                settings.runtime.stop_request_path.unlink(missing_ok=True)
                stop_event = asyncio.Event()
                recovery = MissedPostRecovery(settings, state, fetcher=fetcher, work_lock=daemon.work_lock)
                async with TelegramFeedbackConsumer(settings, state, missed_recovery=recovery) as consumer:
                    async def feedback_loop() -> None:
                        while not stop_event.is_set():
                            try:
                                await consumer.poll_once(
                                    timeout_seconds=settings.notification.telegram_update_poll_seconds
                                )
                            except Exception as exc:
                                LOG.warning("Telegram listener error: %s", exc)
                                await asyncio.sleep(5)

                    async with asyncio.TaskGroup() as tasks:
                        tasks.create_task(_watch_stop_request(settings.runtime.stop_request_path, stop_event), name="stop-watcher")
                        tasks.create_task(daemon.polling_loop(stop_event), name="x-polling")
                        tasks.create_task(feedback_loop(), name="telegram-feedback")
                LOG.info("XListener daemon stopped cooperatively")
    return None
