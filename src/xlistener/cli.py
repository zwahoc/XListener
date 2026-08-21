"""Command-line entry points for setup and ingestion diagnostics."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from .classifier import OllamaTextClassifier
from .config import load_settings
from .daemon import InstanceAlreadyRunning, run_daemon
from .db import SQLiteState
from .fetchers.playwright_x import PlaywrightXFetcher, XAuthenticationRequired
from .learning import learned_prompt_context
from .notification import TelegramFeedbackConsumer, TelegramNotifier, render_notification, should_notify
from .secrets import get_x_credentials
from .supervisor import GamingSupervisor, game_processes_running, unload_ollama_models
from .tray import run_tray


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
    subparsers.add_parser("feedback-listen")
    subparsers.add_parser("run")
    subparsers.add_parser("run-once")
    subparsers.add_parser("supervise")
    subparsers.add_parser("gaming-status")
    subparsers.add_parser("stop")
    subparsers.add_parser("tray")
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
    with SQLiteState(settings.runtime.database_path) as db:
        learned_context = learned_prompt_context(db, settings)
    async with PlaywrightXFetcher(settings) as fetcher:
        tweets = await fetcher.fetch_recent(1)
        if not tweets:
            raise RuntimeError("No posts were returned for classification")
        tweet = await fetcher.enrich_context(tweets[-1])
    classifier = OllamaTextClassifier(settings)
    result, raw_response = await classifier.classify(tweet, learned_context=learned_context, verify=True)
    print(json.dumps({"tweet": tweet.model_dump(mode="json"), "classification": result.model_dump()}, ensure_ascii=True))
    print(json.dumps({"llm_trace": classifier.last_trace.__dict__}, ensure_ascii=True))
    if not raw_response:
        raise RuntimeError("Ollama returned an empty classification response")


async def _notify_latest(settings, dry_run: bool) -> None:
    with SQLiteState(settings.runtime.database_path) as db:
        learned_context = learned_prompt_context(db, settings)
    async with PlaywrightXFetcher(settings) as fetcher:
        tweets = await fetcher.fetch_recent(1)
        if not tweets:
            raise RuntimeError("No posts were returned for notification")
        tweet = await fetcher.enrich_context(tweets[-1])
    classifier = OllamaTextClassifier(settings)
    result, _raw_response = await classifier.classify(tweet, learned_context=learned_context, verify=True)
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
        print(json.dumps({"llm_trace": classifier.last_trace.__dict__}, ensure_ascii=True))
        return
    with SQLiteState(settings.runtime.database_path) as db:
        db.retain_tweet(tweet, "notification", status="classified")
        db.update_tweet_payload(tweet)
        db.save_analysis(tweet.id, result, settings.llm.model, _raw_response)
        async with TelegramNotifier(settings) as notifier:
            message_id = await notifier.send(tweet, result)
        db.record_notification(tweet.id, message_id)
    print(json.dumps({"message_id": message_id, "tweet_id": tweet.id, "llm_trace": classifier.last_trace.__dict__}))


async def _feedback_once(settings) -> None:
    with SQLiteState(settings.runtime.database_path) as db:
        async with TelegramFeedbackConsumer(settings, db) as consumer:
            handled = await consumer.poll_once()
        print(json.dumps({"handled": handled, "next_offset": db.get_telegram_offset()}))


async def _feedback_listen(settings) -> None:
    print("Listening for Telegram ratings and missed-post links. Press Ctrl+C to stop.")
    with SQLiteState(settings.runtime.database_path) as db:
        async with TelegramFeedbackConsumer(settings, db) as consumer:
            while True:
                try:
                    await consumer.poll_once(timeout_seconds=25)
                except (httpx.HTTPError, RuntimeError) as exc:
                    logging.getLogger(__name__).warning("Telegram listener error: %s", exc)
                    await asyncio.sleep(5)


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
        pending_missed = db.connection.execute(
            "SELECT COUNT(*) AS count FROM pending_missed_posts WHERE status = 'pending'"
        ).fetchone()
        queued = db.connection.execute("SELECT COUNT(*) AS count FROM tweets WHERE status = 'queued'").fetchone()
        affinity = db.connection.execute(
            "SELECT tag, score, sample_count FROM tag_affinity ORDER BY ABS(score) DESC, tag"
        ).fetchall()
        print(f"Database: {settings.runtime.database_path}")
        print(f"Cursor: {db.get_cursor() or '<unset>'}")
        print(f"Processed-id checkpoints: {row['count']}")
        print(f"Durable tweets: {durable['count']}")
        print(f"Queued posts: {queued['count']}")
        print(f"Notifications: {notifications['count']}")
        print(f"Feedback ratings: {feedback['count']}")
        print(f"Pending missed-post requests: {pending_missed['count']}")
        print(f"Telegram update offset: {db.get_telegram_offset()}")
        if affinity:
            print("Learned tag affinity:")
            for item in affinity:
                print(f"  {item['tag']}: {float(item['score']):+.2f} ({item['sample_count']} rating(s))")
        else:
            print("Learned tag affinity: <none>")


def main() -> None:
    args = _parser().parse_args()
    settings = load_settings(args.config, args.preferences)
    log_level = getattr(logging, settings.runtime.log_level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    log_path = settings.runtime.supervisor_log_path if args.command == "supervise" else settings.runtime.log_path
    file_handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logging.basicConfig(level=log_level, handlers=[file_handler, console_handler])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
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
        elif args.command == "feedback-listen":
            try:
                asyncio.run(_feedback_listen(settings))
            except KeyboardInterrupt:
                pass
        elif args.command == "run-once":
            result = asyncio.run(run_daemon(settings, once=True))
            print(json.dumps(result.__dict__ if result else {}))
        elif args.command == "run":
            try:
                asyncio.run(run_daemon(settings))
            except KeyboardInterrupt:
                pass
        elif args.command == "supervise":
            try:
                GamingSupervisor(settings).run_forever()
            except KeyboardInterrupt:
                pass
        elif args.command == "gaming-status":
            active = game_processes_running(settings.gaming.processes)
            print(json.dumps({"gaming_enabled": settings.gaming.enabled, "active_game_processes": active}))
        elif args.command == "stop":
            settings.runtime.stop_request_path.touch()
            unloaded = unload_ollama_models(settings) if settings.gaming.unload_ollama_models else []
            print(json.dumps({"stop_requested": True, "unloaded_models": unloaded}))
        elif args.command == "tray":
            run_tray(settings)
    except XAuthenticationRequired as exc:
        raise SystemExit(f"X authentication needs attention: {exc}") from None
    except InstanceAlreadyRunning as exc:
        raise SystemExit(str(exc)) from None
