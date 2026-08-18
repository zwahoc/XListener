from pathlib import Path

from xlistener.fetchers.playwright_x import parse_tweet_articles


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
