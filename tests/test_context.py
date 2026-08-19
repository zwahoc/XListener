from xlistener.context import ContextResolver
from xlistener.models import MediaAsset, RelatedPost, Tweet


def make_tweet(tweet_id: str, text: str, related_posts: list[RelatedPost] | None = None) -> Tweet:
    return Tweet(
        id=tweet_id,
        author_handle="author",
        text=text,
        url=f"https://x.com/author/status/{tweet_id}",
        related_posts=related_posts or [],
        source="test",
    )


async def test_context_resolver_hydrates_and_flattens_nested_posts() -> None:
    nested = RelatedPost(relationship="quoted", id="80", url="https://x.com/nested/status/80")
    parent = make_tweet("90", "Parent text", [nested])
    parent.media = [MediaAsset(kind="image", url="https://pbs.twimg.com/media/parent.jpg")]
    quoted = make_tweet("80", "Nested quote text")
    loaded = {"90": parent, "80": quoted}

    async def load(url: str) -> Tweet | None:
        return loaded.get(url.rsplit("/", 1)[-1])

    monitored = make_tweet(
        "100",
        "Useful reply",
        [RelatedPost(relationship="reply_parent", id="90", url="https://x.com/parent/status/90")],
    ).model_copy(update={"is_reply": True, "context_complete": False})

    result = await ContextResolver(load).resolve(monitored)

    assert [post.id for post in result.related_posts] == ["90", "80"]
    assert result.related_posts[0].text == "Parent text"
    assert result.related_posts[0].media[0].source == "parent"
    assert result.related_posts[1].relationship == "quoted"
    assert result.context_complete is True


async def test_context_resolver_marks_missing_expected_context_incomplete() -> None:
    async def load(_url: str) -> Tweet | None:
        return None

    monitored = make_tweet(
        "100",
        "Short reply",
        [RelatedPost(relationship="reply_parent", id="90", url="https://x.com/parent/status/90")],
    ).model_copy(update={"is_reply": True})

    result = await ContextResolver(load).resolve(monitored)

    assert result.context_complete is False
    assert result.related_posts[0].id == "90"
