"""Command-line entry points for setup and ingestion diagnostics."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from .config import load_settings
from .db import SQLiteState
from .fetchers.playwright_x import PlaywrightXFetcher, XAuthenticationRequired
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
    subparsers.add_parser("db-status")
    return parser


async def _check_browser(settings) -> str:
    async with PlaywrightXFetcher(settings):
        if settings.fetcher.storage_state_path.exists():
            return "Playwright: browser launch and saved session state available"
        return "Playwright: browser launch available; no saved X session yet"


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
        print(f"Database: {settings.runtime.database_path}")
        print(f"Cursor: {db.get_cursor() or '<unset>'}")
        print(f"Processed-id checkpoints: {row['count']}")
        print(f"Durable tweets: {durable['count']}")


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
    except XAuthenticationRequired as exc:
        raise SystemExit(f"X authentication needs attention: {exc}") from None
