from pathlib import Path

from xlistener.fetchers.playwright_x import (
    _apply_graphql_relationships,
    _graphql_tweet_metadata,
    parse_tweet_articles,
)
from xlistener.models import Tweet


FIXTURE = Path(__file__).parent / "fixtures" / "x_profile_articles.html"
RENDERED_FIXTURE = Path(__file__).parent / "fixtures" / "x_profile_rendered_cards.html"


def test_parser_extracts_relationships_and_media() -> None:
    tweets = parse_tweet_articles(FIXTURE.read_text(encoding="utf-8"), "thsottiaux")

    assert [tweet.id for tweet in tweets] == ["100", "101", "102", "103"]
    assert tweets[0].text == "Codex now has a useful reset clarification."
    assert tweets[0].media[0].alt_text == "Reset settings screenshot"
    assert tweets[1].is_reply is True
    assert tweets[1].related_posts[0].relationship == "reply_parent"
    assert tweets[1].related_posts[0].id == "90"
    assert tweets[2].related_posts[0].relationship == "quoted"
    assert tweets[2].related_posts[0].id == "91"
    assert tweets[2].media[0].source == "quoted"
    assert tweets[3].is_repost is True
    assert tweets[3].related_posts[0].relationship == "reposted"


def test_parser_supports_current_rendered_profile_cards() -> None:
    tweets = parse_tweet_articles(RENDERED_FIXTURE.read_text(encoding="utf-8"), "thsottiaux")

    assert [tweet.id for tweet in tweets] == ["200", "201"]
    assert tweets[0].text == "Codex has a new reset detail."
    assert tweets[1].is_reply is True
    assert tweets[1].related_posts[0].id == "190"


def test_graphql_relationships_restore_reply_parent_from_authenticated_timeline() -> None:
    tweets = [
        Tweet(
            id="201",
            author_handle="thsottiaux",
            text="This reply adds useful context.",
            url="https://x.com/thsottiaux/status/201",
            source="test",
        )
    ]
    payload = {
        "data": {
            "user": {
                "result": {
                    "timeline": {
                        "timeline": {
                            "instructions": [
                                {
                                    "entries": [
                                        {
                                            "content": {
                                                "itemContent": {
                                                    "tweet_results": {
                                                        "result": {
                                                            "__typename": "Tweet",
                                                            "rest_id": "201",
                                                            "core": {
                                                                "user_results": {
                                                                    "result": {"core": {"screen_name": "thsottiaux"}}
                                                                }
                                                            },
                                                            "legacy": {
                                                                "in_reply_to_status_id_str": "190",
                                                                "in_reply_to_screen_name": "parent_user",
                                                            },
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

    metadata = _graphql_tweet_metadata(payload)
    enriched = _apply_graphql_relationships(tweets, metadata)
    reply = next(tweet for tweet in enriched if tweet.id == "201")

    assert reply.is_reply is True
    assert str(reply.in_reply_to_url) == "https://x.com/parent_user/status/190"
    assert reply.related_posts[0].relationship == "reply_parent"
    assert reply.related_posts[0].author_handle == "parent_user"
