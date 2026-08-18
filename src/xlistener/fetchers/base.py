"""Fetcher protocol."""

from typing import Protocol

from ..models import Tweet


class TweetFetcher(Protocol):
    async def fetch_recent(self, limit: int = 20) -> list[Tweet]: ...

