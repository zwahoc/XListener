"""Authenticated Playwright fetcher and pure X article parser."""

from __future__ import annotations

import asyncio
import os
import re
import time
import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from ..config import Settings
from ..context import ContextResolver
from ..models import MediaAsset, RelatedPost, Tweet
from ..secrets import ensure_x_credentials


STATUS_RE = re.compile(r"^/[^/]+/status/(\d+)/?$")
HANDLE_RE = re.compile(r"^/@?([A-Za-z0-9_]{1,15})$")
LOG = logging.getLogger(__name__)


class XAuthenticationRequired(RuntimeError):
    """Raised when X requires interactive authentication."""


def _find_chrome_executable() -> str | None:
    """Find an installed Google Chrome executable for manual bootstrap."""

    candidates: list[Path] = []
    if sys.platform == "win32":
        candidates.extend(
            Path(path)
            for path in (
                os.environ.get("PROGRAMFILES", ""),
                os.environ.get("PROGRAMFILES(X86)", ""),
                os.environ.get("LOCALAPPDATA", ""),
            )
            if path
        )
        candidates = [base / "Google/Chrome/Application/chrome.exe" for base in candidates]
    elif sys.platform == "darwin":
        candidates.extend(
            Path(path).expanduser()
            for path in (
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )
        )
    else:
        candidates.extend(Path(path) for path in ("/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"))

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    for command in ("google-chrome", "google-chrome-stable", "chrome"):
        found = shutil.which(command)
        if found:
            return found
    return None


def _status_id(href: str | None) -> str | None:
    if not href:
        return None
    match = STATUS_RE.match(urlparse(href).path)
    return match.group(1) if match else None


def _absolute_url(href: str | None) -> str | None:
    if not href:
        return None
    return urljoin("https://x.com", href)


def _unwrap_graphql_tweet(value: object) -> dict[str, object] | None:
    """Unwrap the visibility wrapper X commonly puts around Tweet results."""

    current = value
    while isinstance(current, dict) and current.get("__typename") in {
        "TweetWithVisibilityResults",
        "TweetWithVisibilityResult",
    }:
        current = current.get("tweet")
    return current if isinstance(current, dict) and current.get("__typename") == "Tweet" else None


def _walk_graphql_tweets(value: object) -> Iterable[dict[str, object]]:
    if isinstance(value, dict):
        tweet_results = value.get("tweet_results")
        if isinstance(tweet_results, dict):
            tweet = _unwrap_graphql_tweet(tweet_results.get("result"))
            if tweet is not None:
                yield tweet
        for child in value.values():
            yield from _walk_graphql_tweets(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_graphql_tweets(child)


def _graphql_tweet_metadata(payload: object) -> dict[str, dict[str, object]]:
    """Extract relationship metadata from an X GraphQL response.

    X's rendered DOM omits reply/quote fields, while the authenticated
    timeline response still exposes them under the legacy Tweet object.
    """

    metadata: dict[str, dict[str, object]] = {}
    for tweet in _walk_graphql_tweets(payload):
        tweet_id = str(tweet.get("rest_id") or "")
        if not tweet_id:
            continue
        legacy = tweet.get("legacy") if isinstance(tweet.get("legacy"), dict) else {}
        core = tweet.get("core") if isinstance(tweet.get("core"), dict) else {}
        user_result = core.get("user_results") if isinstance(core, dict) else None
        user = user_result.get("result") if isinstance(user_result, dict) else None
        user_core = user.get("core") if isinstance(user, dict) else None
        entry: dict[str, object] = {
            "author_handle": user_core.get("screen_name") if isinstance(user_core, dict) else None,
            "reply_id": legacy.get("in_reply_to_status_id_str"),
            "reply_handle": legacy.get("in_reply_to_screen_name"),
            "quote_id": None,
            "quote_handle": None,
            "repost_id": None,
            "repost_handle": None,
        }

        quoted = tweet.get("quoted_status_result")
        quoted_result = quoted.get("result") if isinstance(quoted, dict) else None
        quoted_tweet = _unwrap_graphql_tweet(quoted_result)
        if quoted_tweet:
            entry["quote_id"] = quoted_tweet.get("rest_id")
            quoted_core = quoted_tweet.get("core")
            quoted_user_results = quoted_core.get("user_results") if isinstance(quoted_core, dict) else None
            quoted_user = quoted_user_results.get("result") if isinstance(quoted_user_results, dict) else None
            quoted_user_core = quoted_user.get("core") if isinstance(quoted_user, dict) else None
            entry["quote_handle"] = quoted_user_core.get("screen_name") if isinstance(quoted_user_core, dict) else None

        retweeted = legacy.get("retweeted_status_result") if isinstance(legacy, dict) else None
        if not retweeted:
            retweeted = tweet.get("retweeted_status_result")
        retweeted_result = retweeted.get("result") if isinstance(retweeted, dict) else None
        retweeted_tweet = _unwrap_graphql_tweet(retweeted_result)
        if retweeted_tweet:
            entry["repost_id"] = retweeted_tweet.get("rest_id")
            repost_core = retweeted_tweet.get("core")
            repost_user_results = repost_core.get("user_results") if isinstance(repost_core, dict) else None
            repost_user = repost_user_results.get("result") if isinstance(repost_user_results, dict) else None
            repost_user_core = repost_user.get("core") if isinstance(repost_user, dict) else None
            entry["repost_handle"] = repost_user_core.get("screen_name") if isinstance(repost_user_core, dict) else None

        metadata[tweet_id] = entry
    return metadata


def _apply_graphql_relationships(tweets: list[Tweet], metadata: dict[str, dict[str, object]]) -> list[Tweet]:
    """Merge GraphQL relationships into tweets parsed from the visible DOM."""

    enriched: list[Tweet] = []
    for tweet in tweets:
        info = metadata.get(tweet.id)
        if not info:
            enriched.append(tweet)
            continue
        related = list(tweet.related_posts)

        def add(relationship: str, related_id: object, handle: object) -> None:
            if not related_id or any(post.id == str(related_id) and post.relationship == relationship for post in related):
                return
            related.append(
                RelatedPost(
                    relationship=relationship,
                    id=str(related_id),
                    author_handle=str(handle).lower() if handle else None,
                    url=f"https://x.com/{str(handle).lower() if handle else 'i'}/status/{related_id}",
                )
            )

        add("reply_parent", info.get("reply_id"), info.get("reply_handle"))
        add("quoted", info.get("quote_id"), info.get("quote_handle"))
        add("reposted", info.get("repost_id"), info.get("repost_handle"))
        is_reply = bool(info.get("reply_id")) or tweet.is_reply
        is_repost = bool(info.get("repost_id")) or tweet.is_repost
        enriched.append(
            tweet.model_copy(
                update={
                    "is_reply": is_reply,
                    "in_reply_to_url": next((post.url for post in related if post.relationship == "reply_parent"), None),
                    "is_repost": is_repost,
                    "related_posts": related[:3],
                    "context_complete": tweet.context_complete and (not is_reply or any(post.relationship == "reply_parent" for post in related)),
                    "raw_payload": {**tweet.raw_payload, "graphql_relationships": True},
                }
            )
        )
    return enriched


def _is_status_link(link: Tag) -> bool:
    return _status_id(link.get("href")) is not None


def _in_quote(node: Tag, article: Tag) -> bool:
    parent = node.parent
    while isinstance(parent, Tag) and parent is not article:
        if parent.get("data-testid") == "quoteTweet":
            return True
        parent = parent.parent
    return False


def _text_from_nodes(nodes: Iterable[Tag]) -> str:
    return " ".join(node.get_text(" ", strip=True) for node in nodes if node.get_text(" ", strip=True)).strip()


def _author_handle(article: Tag, monitored_handle: str) -> str:
    user_name = article.select_one('[data-testid="User-Name"]')
    candidates = user_name.select("a[href]") if user_name else article.select("a[href]")
    for link in candidates:
        href = link.get("href", "")
        parsed = urlparse(href)
        path = parsed.path if parsed.scheme else href
        match = HANDLE_RE.match(path.rstrip("/"))
        if match:
            return match.group(1).lower()
    return monitored_handle


def _author_name(article: Tag) -> str | None:
    user_name = article.select_one('[data-testid="User-Name"]')
    if user_name:
        spans = [span.get_text(" ", strip=True) for span in user_name.select("span")]
        name = next((value for value in spans if value and not value.startswith("@")), None)
        if name:
            return name
    for link in article.select("a[href]"):
        href = link.get("href", "")
        path = urlparse(href).path if urlparse(href).scheme else href
        if HANDLE_RE.match(path.rstrip("/")):
            value = link.get_text(" ", strip=True)
            if value and not value.startswith("@"):
                return value
    return None


def _media_from_article(article: Tag) -> list[MediaAsset]:
    media: list[MediaAsset] = []
    seen: set[str] = set()
    for image in article.select("img[src]"):
        url = image.get("src")
        if not url or "pbs.twimg.com/media/" not in url or url in seen:
            continue
        seen.add(url)
        media.append(
            MediaAsset(
                kind="image",
                url=_absolute_url(url),
                alt_text=image.get("alt") or None,
                source="quoted" if _in_quote(image, article) else "direct",
            )
        )
    for video in article.select("video[poster]"):
        poster = video.get("poster")
        if poster and poster not in seen:
            seen.add(poster)
            media.append(MediaAsset(kind="video", url=_absolute_url(poster), source="direct"))
    return media


def _parse_legacy_articles(soup: BeautifulSoup, monitored_handle: str, source: str) -> list[Tweet]:
    tweets: list[Tweet] = []
    for article in soup.select('article[data-testid="tweet"]'):
        status_links = [link for link in article.select('a[href*="/status/"]') if _is_status_link(link)]
        own_link = next((link for link in status_links if not _in_quote(link, article)), None)
        tweet_id = _status_id(own_link.get("href") if own_link else None)
        if not tweet_id:
            continue

        text_nodes = [node for node in article.select('[data-testid="tweetText"]') if not _in_quote(node, article)]
        if not text_nodes:
            text_nodes = article.select('[data-testid="tweetText"]')
        text = _text_from_nodes(text_nodes)
        if not text:
            text = article.get_text(" ", strip=True)

        time_node = article.select_one("time[datetime]")
        created_at = None
        if time_node:
            try:
                created_at = datetime.fromisoformat(time_node["datetime"].replace("Z", "+00:00"))
            except ValueError:
                created_at = None

        relation_links: dict[str, tuple[str, Tag]] = {}
        quote = article.select_one('[data-testid="quoteTweet"]')
        if quote:
            quote_link = next((link for link in quote.select('a[href*="/status/"]') if _is_status_link(link)), None)
            quote_id = _status_id(quote_link.get("href") if quote_link else None)
            if quote_id:
                relation_links["quoted"] = (quote_id, quote_link)

        for link in status_links:
            related_id = _status_id(link.get("href"))
            if not related_id or related_id == tweet_id or _in_quote(link, article):
                continue
            relation_links.setdefault("reposted" if "reposted" in article.get_text(" ", strip=True).lower() else "reply_parent", (related_id, link))

        social_text = " ".join(node.get_text(" ", strip=True) for node in article.select('[data-testid="socialContext"]'))
        full_text_lower = article.get_text(" ", strip=True).lower()
        is_repost = "reposted" in social_text.lower() or " reposted " in f" {full_text_lower} "
        is_reply = "replying to" in full_text_lower or "reply_parent" in relation_links

        related_posts: list[RelatedPost] = []
        for relationship, (related_id, link) in relation_links.items():
            container = link.parent if isinstance(link.parent, Tag) else article
            related_text_nodes = container.select('[data-testid="tweetText"]') if isinstance(container, Tag) else []
            related_posts.append(
                RelatedPost(
                    relationship=relationship,
                    id=related_id,
                    url=_absolute_url(link.get("href")),
                    text=_text_from_nodes(related_text_nodes),
                )
            )

        own_url = _absolute_url(own_link.get("href")) if own_link else f"https://x.com/{monitored_handle}/status/{tweet_id}"
        tweets.append(
            Tweet(
                id=tweet_id,
                author_handle=_author_handle(article, monitored_handle),
                author_name=_author_name(article),
                text=text,
                url=own_url,
                created_at=created_at,
                is_reply=is_reply,
                in_reply_to_url=next((post.url for post in related_posts if post.relationship == "reply_parent"), None),
                media=_media_from_article(article),
                is_repost=is_repost,
                related_posts=related_posts[:3],
                context_complete=not (is_reply and not any(post.relationship == "reply_parent" for post in related_posts)),
                source=source,
                raw_payload={"article_status_links": len(status_links)},
            )
        )
    return tweets


def _profile_cards(soup: BeautifulSoup, monitored_handle: str) -> list[tuple[Tag, Tag]]:
    """Find the largest rendered card containing one canonical status link."""

    cards: list[tuple[Tag, Tag]] = []
    seen_ids: set[str] = set()
    for link in soup.select("a[href]"):
        tweet_id = _status_id(link.get("href"))
        if not tweet_id or tweet_id in seen_ids:
            continue
        path_parts = [part for part in urlparse(link.get("href", "")).path.split("/") if part]
        if not path_parts or path_parts[0].lower() != monitored_handle.lower():
            continue
        selected: Tag | None = None
        for parent in link.parents:
            if not isinstance(parent, Tag) or parent.name != "div":
                continue
            links = [candidate for candidate in parent.select("a[href]") if _status_id(candidate.get("href"))]
            if 1 <= len(links) <= 3 and len(parent.get_text(" ", strip=True)) > len(link.get_text(" ", strip=True)) + 10:
                selected = parent
                classes = set(parent.get("class", []))
                if classes == {"flex", "gap-2"}:
                    break
            elif len(links) > 1:
                break
        if selected:
            seen_ids.add(tweet_id)
            cards.append((selected, link))
    return cards


def _is_engagement_count(value: str) -> bool:
    return bool(re.fullmatch(r"[\d,.]+[KMB]?", value.replace(" ", ""), flags=re.IGNORECASE))


def _parse_rendered_cards(soup: BeautifulSoup, monitored_handle: str, source: str) -> list[Tweet]:
    tweets: list[Tweet] = []
    for card, own_link in _profile_cards(soup, monitored_handle):
        tweet_id = _status_id(own_link.get("href"))
        if not tweet_id:
            continue
        lines = [line.strip() for line in card.get_text("\n", strip=True).splitlines() if line.strip()]
        timestamp = own_link.get_text(" ", strip=True)
        try:
            start = lines.index(timestamp) + 1
        except ValueError:
            start = 0
        content_lines = lines[start:]
        content_lines = [line for line in content_lines if line.lower() != "show more"]
        while content_lines and _is_engagement_count(content_lines[-1]):
            content_lines.pop()
        text = "\n".join(content_lines).strip()

        related_posts: list[RelatedPost] = []
        for link in card.select("a[href]"):
            related_id = _status_id(link.get("href"))
            if related_id and related_id != tweet_id:
                relationship = "reply_parent" if "replying to" in " ".join(lines).lower() else "quoted"
                related_posts.append(
                    RelatedPost(
                        relationship=relationship,
                        id=related_id,
                        url=_absolute_url(link.get("href")),
                    )
                )
                break

        full_text_lower = " ".join(lines).lower()
        is_reply = "replying to" in full_text_lower
        tweets.append(
            Tweet(
                id=tweet_id,
                author_handle=_author_handle(card, monitored_handle),
                author_name=_author_name(card),
                text=text,
                url=_absolute_url(own_link.get("href")),
                is_reply=is_reply,
                in_reply_to_url=next((post.url for post in related_posts if post.relationship == "reply_parent"), None),
                media=_media_from_article(card),
                is_repost="reposted" in full_text_lower,
                related_posts=related_posts,
                context_complete=not (is_reply and not related_posts),
                source=source,
                raw_payload={"rendered_card": True},
            )
        )
    return tweets


def parse_tweet_articles(html: str, monitored_handle: str, source: str = "playwright_x") -> list[Tweet]:
    """Parse legacy X articles or the current rendered profile-card markup."""

    soup = BeautifulSoup(html, "html.parser")
    legacy = _parse_legacy_articles(soup, monitored_handle, source)
    return legacy or _parse_rendered_cards(soup, monitored_handle, source)


class PlaywrightXFetcher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "PlaywrightXFetcher":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        profile = self.settings.fetcher.browser_profile_path
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel=self.settings.fetcher.browser_channel,
            headless=self.settings.fetcher.headless,
        )

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._context = None
        self._browser = None
        self._playwright = None

    async def authenticate(self, manual: bool = False) -> None:
        await self.close()
        if manual:
            await self._bootstrap_manual_profile()
            return

        credentials = ensure_x_credentials()
        if not self._playwright:
            self._playwright = await async_playwright().start()
        profile = self.settings.fetcher.browser_profile_path
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel=self.settings.fetcher.browser_channel,
            headless=False,
        )
        page = await self._context.new_page()
        await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_selector(
            "input[name='username_or_email'], input[autocomplete='username'], input[name='text']",
            timeout=30_000,
        )
        await self._fill_first(
            page,
            ["input[name='username_or_email']", "input[autocomplete='username']", "input[name='text']"],
            credentials[0],
        )
        await self._click_exact_text(page, "Continue")
        await page.wait_for_timeout(1_000)
        await self._raise_for_login_error(page)
        await self._wait_for_visible(
            page,
            ["input[name='password']", "input[autocomplete='current-password']"],
            timeout_seconds=30,
        )
        await self._fill_first(page, ["input[name='password']", "input[autocomplete='current-password']"], credentials[1])
        await self._click_any_exact_text(page, ["Log in", "Sign in", "Continue"])
        print("X login submitted. Complete any challenge or MFA in the browser window if shown.")
        await self._wait_for_login_completion(page, timeout_seconds=180)
        await self._save_authenticated_state(page)

    async def _bootstrap_manual_profile(self) -> None:
        chrome = _find_chrome_executable()
        if not chrome:
            raise XAuthenticationRequired("Google Chrome is not installed or could not be found")

        profile = self.settings.fetcher.browser_profile_path
        profile.mkdir(parents=True, exist_ok=True)
        browser_process = subprocess.Popen(
            [
                chrome,
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "https://x.com/i/flow/login",
            ]
        )
        print(f"Opened ordinary Google Chrome with the dedicated XListener profile: {profile}")
        print("Complete the X login, then close every window belonging to that profile.")
        try:
            await asyncio.wait_for(asyncio.to_thread(browser_process.wait), timeout=600)
        except asyncio.TimeoutError:
            browser_process.terminate()
            raise XAuthenticationRequired("Timed out waiting for the dedicated Chrome profile to close") from None

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel=self.settings.fetcher.browser_channel,
            headless=False,
        )
        page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        await self._save_authenticated_state(page)

    async def _save_authenticated_state(self, page: Page) -> None:
        await page.goto(self.settings.account.profile_url, wait_until="domcontentloaded", timeout=45_000)
        if "/i/flow/login" in page.url or "/login" in page.url:
            raise XAuthenticationRequired("X login did not complete; finish the browser challenge and rerun auth-x")
        await page.wait_for_selector('article[data-testid="tweet"]', timeout=30_000)
        self.settings.fetcher.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=str(self.settings.fetcher.storage_state_path))
        print(f"Saved Playwright session state to {self.settings.fetcher.storage_state_path}")

    @staticmethod
    async def _raise_for_login_error(page: Page) -> None:
        body = (await page.locator("body").inner_text()).lower()
        if "temporarily limited your login" in body:
            raise XAuthenticationRequired("X has temporarily limited login attempts; wait before trying auth-x again")

    @classmethod
    async def _wait_for_login_completion(cls, page: Page, timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            await cls._raise_for_login_error(page)
            if "/i/flow/login" not in page.url and "/i/jf/onboarding" not in page.url and "/login" not in page.url:
                return
            await page.wait_for_timeout(1_000)
        raise XAuthenticationRequired("Timed out waiting for X login or challenge completion")

    @staticmethod
    async def _wait_for_visible(page: Page, selectors: list[str], timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            for selector in selectors:
                locator = page.locator(selector)
                for index in range(await locator.count()):
                    if await locator.nth(index).is_visible():
                        return
            await page.wait_for_timeout(250)
        raise XAuthenticationRequired(f"Timed out waiting for visible login field: {selectors}")

    @staticmethod
    async def _fill_first(page: Page, selectors: list[str], value: str) -> None:
        for selector in selectors:
            locator = page.locator(selector)
            for index in range(await locator.count()):
                candidate = locator.nth(index)
                if await candidate.is_visible():
                    await candidate.fill(value)
                    return
        raise XAuthenticationRequired(f"Could not find login field: {selectors}")

    @staticmethod
    async def _click_first(page: Page, selectors: list[str]) -> None:
        for selector in selectors:
            locator = page.locator(selector)
            for index in range(await locator.count()):
                candidate = locator.nth(index)
                if await candidate.is_visible() and await candidate.is_enabled():
                    await candidate.click()
                    return
        raise XAuthenticationRequired(f"Could not find login button: {selectors}")

    @staticmethod
    async def _click_exact_text(page: Page, label: str) -> None:
        locator = page.get_by_text(label, exact=True)
        for index in range(await locator.count()):
            candidate = locator.nth(index)
            if await candidate.is_visible():
                await candidate.click()
                return
        raise XAuthenticationRequired(f"Could not find visible login action: {label}")

    @classmethod
    async def _click_any_exact_text(cls, page: Page, labels: list[str]) -> None:
        for label in labels:
            try:
                await cls._click_exact_text(page, label)
                return
            except XAuthenticationRequired:
                continue
        raise XAuthenticationRequired(f"Could not find visible login action: {labels}")

    async def _fetch_page(self, page: Page, url: str) -> list[Tweet]:
        graphql_payloads: list[object] = []
        response_tasks: list[asyncio.Task[None]] = []

        async def capture_response(response) -> None:
            if "/i/api/graphql/" not in response.url:
                return
            operation = response.url.split("/graphql/", 1)[-1].split("?", 1)[0]
            if operation in {"DataSaverMode", "SidebarUserRecommendations", "ExploreSidebar", "ProfileSpotlightsQuery"}:
                return
            try:
                graphql_payloads.append(await response.json())
            except Exception:
                return

        def on_response(response) -> None:
            response_tasks.append(asyncio.create_task(capture_response(response)))

        page.on("response", on_response)
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        if "/i/flow/login" in page.url or "/login" in page.url:
            raise XAuthenticationRequired("Saved X session is expired")
        try:
            await page.wait_for_selector('article[data-testid="tweet"], a[href*="/status/"]', timeout=15_000)
        except Exception:
            content = await page.content()
            if "Something went wrong" in content or "Log in" in content:
                raise RuntimeError("X profile did not expose tweet articles; session or selectors may have changed")
        # Timeline GraphQL responses arrive just after the initial DOM. Give
        # the response handlers a short bounded window, then merge metadata.
        await page.wait_for_timeout(1_000)
        if response_tasks:
            await asyncio.gather(*response_tasks, return_exceptions=True)
        parsed = parse_tweet_articles(await page.content(), self.settings.account.handle)
        metadata: dict[str, dict[str, object]] = {}
        for payload in graphql_payloads:
            metadata.update(_graphql_tweet_metadata(payload))
        return _apply_graphql_relationships(parsed, metadata)

    async def fetch_recent(self, limit: int = 20) -> list[Tweet]:
        if not self._context:
            await self.start()
        try:
            return await self._fetch_recent_once(limit)
        except XAuthenticationRequired:
            await self.authenticate()
            return await self._fetch_recent_once(limit)

    async def fetch_post(self, url: str) -> Tweet | None:
        """Fetch one canonical status page and return the requested post."""

        if not self._context:
            await self.start()
        try:
            return await self._fetch_post_once(url)
        except XAuthenticationRequired:
            await self.authenticate()
            return await self._fetch_post_once(url)

    async def _fetch_post_once(self, url: str) -> Tweet | None:
        assert self._context is not None
        requested_id = _status_id(url)
        page = await self._context.new_page()
        try:
            parsed = await self._fetch_page(page, url)
        finally:
            await page.close()
        if requested_id:
            return next((tweet for tweet in parsed if tweet.id == requested_id), None)
        return parsed[0] if parsed else None

    async def enrich_context(self, tweet: Tweet) -> Tweet:
        """Hydrate a bounded reply/quote/repost relationship bundle."""

        return await ContextResolver(self.fetch_post, max_depth=2, max_related=3).resolve(tweet)

    async def _fetch_recent_once(self, limit: int) -> list[Tweet]:
        assert self._context is not None
        page = await self._context.new_page()
        urls = [self.settings.account.profile_url]
        if self.settings.fetcher.include_replies:
            urls.append(f"{self.settings.account.profile_url}/with_replies")
        collected: dict[str, Tweet] = {}
        try:
            for index, url in enumerate(urls):
                try:
                    parsed = await self._fetch_page(page, url)
                except (RuntimeError, XAuthenticationRequired) as exc:
                    if index == 0 or not collected:
                        raise
                    LOG.warning("optional X timeline unavailable for %s: %s", url, exc)
                    continue
                for tweet in parsed:
                    collected[tweet.id] = tweet
        finally:
            await page.close()

        def sort_key(tweet: Tweet) -> tuple[float, int]:
            created = tweet.created_at.timestamp() if tweet.created_at else 0.0
            try:
                numeric_id = int(tweet.id)
            except ValueError:
                numeric_id = 0
            return created, numeric_id

        return sorted(collected.values(), key=sort_key)[-limit:]
