import json

import pytest

from xlistener.classifier import ClassificationError, OllamaTextClassifier, build_context_bundle, build_messages
from xlistener.config import load_settings
from xlistener.models import RelatedPost, Tweet


class FakeOllamaClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[dict] = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": {"content": self.responses.pop(0)}}


def reply_tweet() -> Tweet:
    return Tweet(
        id="100",
        author_handle="monitor",
        text="The reset is weekly now.",
        url="https://x.com/monitor/status/100",
        is_reply=True,
        related_posts=[
            RelatedPost(
                relationship="reply_parent",
                id="90",
                author_handle="someone",
                text="When does the Codex allowance reset?",
                url="https://x.com/someone/status/90",
            )
        ],
        source="test",
    )


def test_context_bundle_labels_nested_posts() -> None:
    bundle = build_context_bundle(reply_tweet())

    assert "[MONITORED_REPLY]" in bundle
    assert "[REPLY_PARENT]" in bundle
    assert "When does the Codex allowance reset?" in bundle


def test_prompt_treats_post_as_untrusted_data(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    messages = build_messages(reply_tweet(), settings)

    assert "untrusted data" in messages[0]["content"]
    assert "allowed tags" in messages[0]["content"].lower()


async def test_classifier_validates_structured_result_and_normalizes_tags(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    response = json.dumps(
        {
            "relevant": True,
            "importance": 9,
            "topic": "Codex reset timing",
            "tags": ["Codex", "Reset", "reset"],
            "reason": "This directly changes reset timing.",
            "summary": "Codex allowance now resets weekly.",
        }
    )
    client = FakeOllamaClient([response])

    result, raw = await OllamaTextClassifier(settings, client).classify(reply_tweet())

    assert result.tags == ["codex", "reset"]
    assert result.importance == 9
    assert raw == response
    assert client.calls[0]["think"] is False
    assert isinstance(client.calls[0]["format"], dict)


async def test_classifier_repairs_invalid_first_response(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    valid = json.dumps(
        {
            "relevant": False,
            "importance": 2,
            "topic": "Routine conversation",
            "tags": ["conversation"],
            "reason": "No product information is present.",
            "summary": "Routine conversation.",
        }
    )
    client = FakeOllamaClient(["not-json", valid])

    result, _raw = await OllamaTextClassifier(settings, client).classify(reply_tweet())

    assert result.relevant is False
    assert len(client.calls) == 2
    assert "previous response was invalid" in client.calls[1]["messages"][1]["content"].lower()


async def test_classifier_fails_after_two_invalid_responses(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    client = FakeOllamaClient(["bad", '{"relevant": true}'])

    with pytest.raises(ClassificationError):
        await OllamaTextClassifier(settings, client).classify(reply_tweet())
