"""Bounded hydration of reply, quote, and repost context."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .models import MediaAsset, RelatedPost, Tweet


PostLoader = Callable[[str], Awaitable[Tweet | None]]


def _related_key(post: RelatedPost) -> str | None:
    if post.id:
        return f"id:{post.id}"
    if post.url:
        return f"url:{post.url}"
    return None


def _media_for_relationship(media: list[MediaAsset], relationship: str) -> list[MediaAsset]:
    source = "quoted" if relationship == "quoted" else "parent"
    return [item.model_copy(update={"source": source}) for item in media]


class ContextResolver:
    """Resolve a small, labeled relationship graph without crawling a thread."""

    def __init__(self, load_post: PostLoader, max_depth: int = 2, max_related: int = 3):
        self.load_post = load_post
        self.max_depth = max_depth
        self.max_related = max_related

    async def resolve(self, tweet: Tweet) -> Tweet:
        resolved: list[RelatedPost] = []
        seen = {f"id:{tweet.id}", f"url:{tweet.url}"}
        expects_context = tweet.is_reply or tweet.is_repost or bool(tweet.related_posts)
        context_complete = True if expects_context else tweet.context_complete

        async def visit(post: RelatedPost, depth: int) -> None:
            nonlocal context_complete
            if len(resolved) >= self.max_related:
                return
            key = _related_key(post)
            if key and key in seen:
                return
            if key:
                seen.add(key)

            loaded: Tweet | None = None
            if post.url:
                try:
                    loaded = await self.load_post(str(post.url))
                except Exception:
                    context_complete = False

            if loaded is None and not post.text:
                context_complete = False

            hydrated = post
            if loaded is not None:
                hydrated = RelatedPost(
                    relationship=post.relationship,
                    id=post.id or loaded.id,
                    author_handle=loaded.author_handle,
                    text=loaded.text or post.text,
                    url=post.url or loaded.url,
                    media=_media_for_relationship(loaded.media, post.relationship),
                )
            resolved.append(hydrated)

            if loaded is not None and depth < self.max_depth:
                for nested in loaded.related_posts:
                    if len(resolved) >= self.max_related:
                        break
                    await visit(nested, depth + 1)

        for related in tweet.related_posts:
            if len(resolved) >= self.max_related:
                break
            await visit(related, 1)

        if expects_context and not resolved:
            context_complete = False
        return tweet.model_copy(update={"related_posts": resolved, "context_complete": context_complete})
