"""Command-line entry points for setup and ingestion diagnostics."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from .classifier import OllamaTextClassifier
from .config import load_settings
from .db import SQLiteState
from .fetchers.playwright_x import PlaywrightXFetcher, XAuthenticationRequired
from .notification import TelegramFeedbackConsumer, TelegramNotifier, render_notification, should_notify
from .secrets import get_x_credentials


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xlistener")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--preferences", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    auth = subparsers.add_parser("auth-x")
    auth.add_argument("--manual", action="store_true")
    fetch = subparsers.add_parser("fetch-once")
    fetch.add_argument("--limit", type=int, default=None)
    subparsers.add_parser("classify-latest")
    notify = subparsers.add_parser("notify-latest")
    notify.add_argument("--dry-run", action="store_true")
    subparsers.add_parser("feedback-once")
    subparsers.add_parser("db-status")
    return parser


async def _check_browser(settings) -> str:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel=settings.fetcher.browser_channel,
            headless=True,
        )
        await browser.close()
    if settings.fetcher.storage_state_path.exists():
        return "Playwright: installed Chrome launch and saved session marker available"
    return "Playwright: installed Chrome launch available; no saved X session yet"


async def _auth_x(settings, manual: bool) -> None:
    fetcher = PlaywrightXFetcher(settings)
    try:
        await fetcher.authenticate(manual=manual)
    finally:
        await fetcher.close()


async def _fetch_once(settings, limit: int | None) -> None:
    async with PlaywrightXFetcher(settings) as fetcher:
        tweets = await fetcher.fetch_recent(limit or settings.fetcher.max_posts_per_poll)
    for tweet in tweets:
        print(json.dumps(tweet.model_dump(mode="json"), ensure_ascii=True))


async def _classify_latest(settings) -> None:
    async with PlaywrightXFetcher(settings) as fetcher:
        tweets = await fetcher.fetch_recent(1)
        if not tweets:
            raise RuntimeError("No posts were returned for classification")
        tweet = await fetcher.enrich_context(tweets[-1])
    result, raw_response = await OllamaTextClassifier(settings).classify(tweet)
    print(json.dumps({"tweet": tweet.model_dump(mode="json"), "classification": result.model_dump()}, ensure_ascii=True))
    if not raw_response:
        raise RuntimeError("Ollama returned an empty classification response")


async def _notify_latest(settings, dry_run: bool) -> None:
    async with PlaywrightXFetcher(settings) as fetcher:
        tweets = await fetcher.fetch_recent(1)
        if not tweets:
            raise RuntimeError("No posts were returned for notification")
        tweet = await fetcher.enrich_context(tweets[-1])
    result, _raw_response = await OllamaTextClassifier(settings).classify(tweet)
    if not should_notify(result, settings):
        print(
            json.dumps(
                {
                    "status": "skipped",
                    "tweet_id": tweet.id,
                    "relevant": result.relevant,
                    "importance": result.importance,
                    "threshold": settings.notification.min_importance,
                    "tags": result.tags,
                }
            )
        )
        return
    if dry_run or settings.runtime.dry_run:
        print(render_notification(tweet, result, model_name=settings.llm.model))
        return
    with SQLiteState(settings.runtime.database_path) as db:
        db.retain_tweet(tweet, "notification", status="classified")
        db.save_analysis(tweet.id, result, settings.llm.model, _raw_response)
        async with TelegramNotifier(settings) as notifier:
            message_id = await notifier.send(tweet, result)
        db.record_notification(tweet.id, message_id)
    print(json.dumps({"message_id": message_id, "tweet_id": tweet.id}))


async def _feedback_once(settings) -> None:
    with SQLiteState(settings.runtime.database_path) as db:
        async with TelegramFeedbackConsumer(settings, db) as consumer:
            handled = await consumer.poll_once()
        print(json.dumps({"handled": handled, "next_offset": db.get_telegram_offset()}))


def _check(settings) -> None:
    print(f"Config: account=@{settings.account.handle}")
    print(f"Database: {settings.runtime.database_path}")
    print(f"X credentials present: {get_x_credentials() is not None}")
    try:
        response = httpx.get(f"{settings.llm.base_url}/api/version", timeout=10)
        response.raise_for_status()
        print(f"Ollama: {response.json().get('version', 'reachable')}")
    except Exception as exc:
        print(f"Ollama: unavailable ({exc})")
    print(f"Telegram token present: {bool(settings.telegram_bot_token)}")
    print(f"Telegram chat id present: {bool(settings.telegram_chat_id)}")
    print(asyncio.run(_check_browser(settings)))


def _db_status(settings) -> None:
    with SQLiteState(settings.runtime.database_path) as db:
        row = db.connection.execute("SELECT COUNT(*) AS count FROM processed_ids").fetchone()
        durable = db.connection.execute("SELECT COUNT(*) AS count FROM tweets").fetchone()
        notifications = db.connection.execute("SELECT COUNT(*) AS count FROM notifications").fetchone()
        feedback = db.connection.execute("SELECT COUNT(*) AS count FROM feedback").fetchone()
        print(f"Database: {settings.runtime.database_path}")
        print(f"Cursor: {db.get_cursor() or '<unset>'}")
        print(f"Processed-id checkpoints: {row['count']}")
        print(f"Durable tweets: {durable['count']}")
        print(f"Notifications: {notifications['count']}")
        print(f"Feedback ratings: {feedback['count']}")
        print(f"Telegram update offset: {db.get_telegram_offset()}")


def main() -> None:
    args = _parser().parse_args()
    settings = load_settings(args.config, args.preferences)
    try:
        if args.command == "check":
            _check(settings)
        elif args.command == "db-status":
            _db_status(settings)
        elif args.command == "auth-x":
            asyncio.run(_auth_x(settings, args.manual))
        elif args.command == "fetch-once":
            asyncio.run(_fetch_once(settings, args.limit))
        elif args.command == "classify-latest":
            asyncio.run(_classify_latest(settings))
        elif args.command == "notify-latest":
            asyncio.run(_notify_latest(settings, args.dry_run))
        elif args.command == "feedback-once":
            asyncio.run(_feedback_once(settings))
    except XAuthenticationRequired as exc:
        raise SystemExit(f"X authentication needs attention: {exc}") from None
