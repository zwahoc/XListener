"""User-submitted missed-post recovery."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .classifier import OllamaTextClassifier
from .config import Settings
from .db import SQLiteState
from .fetchers.playwright_x import PlaywrightXFetcher
from .learning import learned_prompt_context, refresh_learning_profile
from .models import ClassificationResult, Tweet


@dataclass(frozen=True)
class MissedPostOutcome:
    tweet: Tweet
    result: ClassificationResult
    rating: int


class MissedPostError(RuntimeError):
    """Raised when a submitted missed post cannot be recovered."""


class MissedPostRecovery:
    def __init__(
        self,
        settings: Settings,
        state: SQLiteState,
        fetcher: Any | None = None,
        work_lock: asyncio.Lock | None = None,
    ):
        self.settings = settings
        self.state = state
        self.fetcher = fetcher
        self.work_lock = work_lock

    async def process(self, url: str, rating: int) -> MissedPostOutcome:
        if self.work_lock is not None:
            async with self.work_lock:
                return await self._process_unlocked(url, rating)
        return await self._process_unlocked(url, rating)

    async def _process_unlocked(self, url: str, rating: int) -> MissedPostOutcome:
        learned_context = learned_prompt_context(self.state, self.settings)
        if self.fetcher is None:
            async with PlaywrightXFetcher(self.settings) as fetcher:
                tweet = await fetcher.fetch_post(url)
                if tweet is None:
                    raise MissedPostError("X did not return the submitted post")
                if tweet.author_handle.lower() != self.settings.account.handle.lower():
                    raise MissedPostError(
                        f"The submitted post is by @{tweet.author_handle}, not the monitored account @{self.settings.account.handle}"
                    )
                tweet = await fetcher.enrich_context(tweet)
        else:
            fetcher = self.fetcher
            tweet = await fetcher.fetch_post(url)
            if tweet is None:
                raise MissedPostError("X did not return the submitted post")
            if tweet.author_handle.lower() != self.settings.account.handle.lower():
                raise MissedPostError(
                    f"The submitted post is by @{tweet.author_handle}, not the monitored account @{self.settings.account.handle}"
                )
            tweet = await fetcher.enrich_context(tweet)

        classifier = OllamaTextClassifier(self.settings)
        result, raw_response = await classifier.classify(
            tweet,
            learned_context=learned_context,
            verify=True,
        )
        self.state.retain_tweet(tweet, "user_submitted_missed", status="classified")
        self.state.update_tweet_payload(tweet)
        self.state.save_analysis(tweet.id, result, self.settings.llm.model, raw_response)
        self.state.save_feedback(tweet.id, rating, source="missed_post")
        self.state.record_processed_id(
            tweet.id,
            "false_negative_recovered" if rating > 5 else "user_submitted_reviewed",
            retention_days=self.settings.learning.processed_id_retention_days,
        )
        if self.settings.learning.enabled:
            refresh_learning_profile(self.state, self.settings)

        return MissedPostOutcome(tweet=tweet, result=result, rating=rating)
