"""Telegram notification rendering and delivery."""

from __future__ import annotations

import asyncio
import html
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx

from .config import Settings
from .db import SQLiteState
from .models import ClassificationResult, Tweet


class NotificationError(RuntimeError):
    """Raised when Telegram rejects or cannot receive a notification."""


class TelegramClient(Protocol):
    async def post(self, url: str, **kwargs: Any) -> Any: ...


def should_notify(result: ClassificationResult, settings: Settings) -> bool:
    return result.relevant and result.importance >= settings.notification.min_importance


def _clip(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "..."


MALAYSIA_TIME = timezone(timedelta(hours=8), "MYT")


def _profile_link(handle: str | None) -> str:
    if not handle:
        return "@unknown"
    normalized = handle.lstrip("@")
    label = html.escape(f"@{normalized}")
    url = html.escape(f"https://x.com/{normalized}", quote=True)
    return f'<a href="{url}">{label}</a>'


def _opening_line(tweet: Tweet) -> str:
    author = _profile_link(tweet.author_handle)
    if tweet.is_repost:
        original = next((post for post in tweet.related_posts if post.relationship == "reposted"), None)
        return f"Repost by {author} from {_profile_link(original.author_handle if original else None)}"
    if tweet.is_reply:
        parent = next((post for post in tweet.related_posts if post.relationship == "reply_parent"), None)
        return f"Replied by {author} to {_profile_link(parent.author_handle if parent else None)}"
    return f"Original post by {author}"


def _format_malaysia_time(value: datetime | None) -> str:
    if value is None:
        return "Unavailable"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MALAYSIA_TIME).strftime("%d %b %Y, %I:%M %p MYT").lstrip("0")


def render_notification(
    tweet: Tweet,
    result: ClassificationResult,
    model_name: str = "local model",
    notified_at: datetime | None = None,
    max_length: int = 4096,
) -> str:
    """Render a Telegram-safe HTML message under Telegram's length limit."""

    tags = ", ".join(result.tags) if result.tags else "none"
    lines = [
        _opening_line(tweet),
        "",
        "<b>Summary</b>",
        html.escape(_clip(result.summary, 1_400)),
        "",
        f"<b>Reasoning from {html.escape(model_name)}</b>",
        html.escape(_clip(result.reason, 1_000)),
        "",
        f"<b>Importance:</b> {result.importance}/10",
        f"<b>Tags:</b> {html.escape(tags)}",
        "",
        "<b>Timestamp</b>",
        f"Posted: {_format_malaysia_time(tweet.created_at)}",
        f"Notified: {_format_malaysia_time(notified_at or datetime.now(timezone.utc))}",
        "",
        f'<a href="{html.escape(str(tweet.url), quote=True)}">View tweet</a>',
    ]
    rendered = "\n".join(lines)
    return rendered if len(rendered) <= max_length else rendered[: max_length - 3].rstrip() + "..."


def rating_keyboard(tweet_id: str) -> dict[str, list[list[dict[str, str]]]]:
    buttons = [
        {"text": str(score), "callback_data": f"rate:{tweet_id}:{score}"}
        for score in range(1, 11)
    ]
    return {"inline_keyboard": [buttons[:5], buttons[5:]]}


def parse_rating_callback(value: str) -> tuple[str, int] | None:
    parts = value.split(":")
    if len(parts) != 3 or parts[0] != "rate" or not parts[1].isdigit() or not parts[2].isdigit():
        return None
    rating = int(parts[2])
    return (parts[1], rating) if 1 <= rating <= 10 else None


class TelegramNotifier:
    def __init__(
        self,
        settings: Settings,
        client: TelegramClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            base_url=f"https://api.telegram.org/bot{settings.telegram_bot_token or ''}",
            timeout=20,
        )
        self._owns_client = client is None
        self._sleep = sleep

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()  # type: ignore[attr-defined]

    async def __aenter__(self) -> "TelegramNotifier":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    async def send(self, tweet: Tweet, result: ClassificationResult) -> str:
        if not should_notify(result, self.settings):
            raise NotificationError("classification is below the notification threshold")
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            raise NotificationError("Telegram bot token and chat id are required")

        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": render_notification(tweet, result, model_name=self.settings.llm.model),
            "parse_mode": self.settings.notification.parse_mode,
            "disable_web_page_preview": False,
        }
        if self.settings.notification.feedback_enabled:
            payload["reply_markup"] = rating_keyboard(tweet.id)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.post("/sendMessage", json=payload)
                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
                data = response.json() if hasattr(response, "json") else response
                if not data.get("ok"):
                    raise NotificationError(str(data.get("description", "Telegram rejected the message")))
                message_id = data.get("result", {}).get("message_id")
                if message_id is None:
                    raise NotificationError("Telegram response did not include a message id")
                return str(message_id)
            except (httpx.HTTPError, NotificationError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    await self._sleep(2**attempt)
        raise NotificationError(f"Telegram delivery failed after 3 attempts: {last_error}") from last_error


class TelegramFeedbackConsumer:
    """Consume private inline rating callbacks with a durable update offset."""

    def __init__(self, settings: Settings, state: SQLiteState, client: TelegramClient | None = None):
        self.settings = settings
        self.state = state
        self.client = client or httpx.AsyncClient(
            base_url=f"https://api.telegram.org/bot{settings.telegram_bot_token or ''}",
            timeout=35,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()  # type: ignore[attr-defined]

    async def __aenter__(self) -> "TelegramFeedbackConsumer":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    async def poll_once(self, timeout_seconds: int = 0) -> int:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            raise NotificationError("Telegram bot token and chat id are required")
        response = await self.client.post(
            "/getUpdates",
            json={
                "offset": self.state.get_telegram_offset(),
                "timeout": timeout_seconds,
                "allowed_updates": ["callback_query"],
            },
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        data = response.json() if hasattr(response, "json") else response
        if not data.get("ok"):
            raise NotificationError(str(data.get("description", "Telegram rejected getUpdates")))

        handled = 0
        for update in data.get("result", []):
            update_id = int(update["update_id"])
            callback = update.get("callback_query") or {}
            await self._handle_callback(callback, str(update_id))
            self.state.set_telegram_offset(update_id + 1)
            handled += 1
        return handled

    async def _handle_callback(self, callback: dict[str, Any], update_id: str) -> None:
        callback_id = str(callback.get("id") or "")
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        if str(chat.get("id")) != str(self.settings.telegram_chat_id):
            if callback_id:
                await self._answer_callback(callback_id, "This rating is not accepted here.", alert=True)
            return

        parsed = parse_rating_callback(str(callback.get("data") or ""))
        if not parsed:
            if callback_id:
                await self._answer_callback(callback_id, "This rating button is invalid.", alert=True)
            return
        tweet_id, rating = parsed
        exists = self.state.connection.execute("SELECT 1 FROM tweets WHERE id = ?", (tweet_id,)).fetchone()
        if not exists:
            if callback_id:
                await self._answer_callback(callback_id, "This post is no longer available.", alert=True)
            return
        self.state.save_feedback(tweet_id, rating, telegram_update_id=update_id)
        if callback_id:
            await self._answer_callback(callback_id, f"Saved rating: {rating}/10")

    async def _answer_callback(self, callback_id: str, text: str, alert: bool = False) -> None:
        response = await self.client.post(
            "/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text, "show_alert": alert},
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
