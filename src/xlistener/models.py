"""Domain models shared by ingestion, persistence, and later pipeline stages."""

from datetime import datetime
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, Field


class MediaAsset(BaseModel):
    kind: Literal["image", "video", "gif"]
    url: AnyHttpUrl
    alt_text: str | None = None
    source: Literal["direct", "quoted", "parent"] = "direct"


class RelatedPost(BaseModel):
    relationship: Literal["reply_parent", "quoted", "reposted"]
    id: str | None = None
    author_handle: str | None = None
    text: str = ""
    url: AnyHttpUrl | None = None
    media: list[MediaAsset] = Field(default_factory=list)


class Tweet(BaseModel):
    id: str
    author_handle: str
    author_name: str | None = None
    text: str
    url: AnyHttpUrl
    created_at: datetime | None = None
    is_reply: bool = False
    in_reply_to_url: AnyHttpUrl | None = None
    media: list[MediaAsset] = Field(default_factory=list)
    is_repost: bool = False
    related_posts: list[RelatedPost] = Field(default_factory=list)
    context_complete: bool = True
    source: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    relevant: bool
    importance: int = Field(ge=1, le=10)
    topic: str
    tags: list[str] = Field(default_factory=list, max_length=8)
    reason: str
    summary: str

