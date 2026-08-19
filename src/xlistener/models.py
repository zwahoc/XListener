"""Domain models shared by ingestion, persistence, and later pipeline stages."""

from datetime import datetime
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


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
    tags: list[str] = Field(min_length=1, max_length=8)
    tone: Literal["literal", "sarcastic", "humorous", "promotional", "conversational", "critical", "uncertain"] = "uncertain"
    stance: Literal["supportive", "critical", "neutral", "questioning", "contradictory", "uncertain"] = "uncertain"
    reason: str
    summary: str

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[str] = []
        for item in value:
            tag = str(item).strip().lower().replace("-", "_").replace(" ", "_")
            if tag and tag not in normalized:
                normalized.append(tag)
        return normalized

    @field_validator("topic", "reason", "summary")
    @classmethod
    def require_nonempty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("classification text fields cannot be empty")
        return stripped
