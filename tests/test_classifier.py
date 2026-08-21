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
    assert "model-generated" in messages[0]["content"].lower()
    assert "fixed vocabulary" in messages[0]["content"].lower()


def test_prompt_includes_author_entity_and_reply_first_guidance(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    messages = build_messages(reply_tweet(), settings)

    prompt = messages[1]["content"]
    assert "Tibo" in prompt
    assert "Claude Code" in prompt
    assert "Opus 5" in prompt
    assert "Codex-CLI" in prompt
    assert "Strongest overlap with OpenAI" in prompt
    assert "@claudedevs" in prompt
    assert "primary evidence" in prompt.lower()
    assert "tone" in messages[0]["content"].lower()
    assert "must be meaningfully different" in messages[0]["content"].lower()
    assert "do not retell the post" in messages[0]["content"].lower()


def test_context_bundle_resolves_related_author_to_known_entity(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    tweet = Tweet(
        id="100",
        author_handle="thsottiaux",
        text="Do not worry, we have compute",
        url="https://x.com/thsottiaux/status/100",
        is_reply=True,
        related_posts=[
            RelatedPost(
                relationship="reply_parent",
                author_handle="claudedevs",
                text="We are extending Claude Code limits.",
                url="https://x.com/claudedevs/status/90",
            )
        ],
        source="test",
    )

    bundle = build_context_bundle(tweet, settings)

    assert "author: @claudedevs" in bundle
    assert "known_entity: Anthropic" in bundle
    assert "known_entity_products: Claude, Claude Code, Opus 5, Fable 5" in bundle


def test_prompt_includes_learned_preference_guidance(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    messages = build_messages(reply_tweet(), settings, learned_context="LEARNED TAG AFFINITY:\n- reset: +0.80")

    assert "reset: +0.80" in messages[1]["content"]
    assert "must not override" in messages[1]["content"]


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
    assert client.calls[0]["think"] is True
    assert isinstance(client.calls[0]["format"], dict)


async def test_classifier_accepts_model_generated_tags(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    response = json.dumps(
        {
            "relevant": True,
            "importance": 8,
            "topic": "Agent workflow",
            "tags": ["Agent Workflow", "Long-Context Reasoning"],
            "reason": "The post describes a useful new agent workflow.",
            "summary": "A new agent workflow is available.",
        }
    )

    result, _raw = await OllamaTextClassifier(settings, FakeOllamaClient([response])).classify(reply_tweet())

    assert result.tags == ["agent_workflow", "long_context_reasoning"]


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


async def test_classifier_repairs_duplicate_summary_and_reason(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    duplicate = json.dumps(
        {
            "relevant": True,
            "importance": 8,
            "topic": "Codex reset",
            "tags": ["codex", "reset"],
            "reason": "Codex users receive an additional reset this week.",
            "summary": "Codex users receive an additional reset this week.",
        }
    )
    corrected = json.dumps(
        {
            "relevant": True,
            "importance": 8,
            "topic": "Codex reset",
            "tags": ["codex", "reset"],
            "reason": "This directly matches the user's interest in reset timing and has an immediate practical effect on available usage.",
            "summary": "Codex users receive an additional reset this week.",
        }
    )
    client = FakeOllamaClient([duplicate, corrected])

    result, _raw = await OllamaTextClassifier(settings, client).classify(reply_tweet())

    assert result.reason != result.summary
    assert len(client.calls) == 2
    assert "identical or near-identical" in client.calls[1]["messages"][1]["content"]


async def test_classifier_fails_after_two_invalid_responses(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    client = FakeOllamaClient(["bad", '{"relevant": true}'])

    with pytest.raises(ClassificationError):
        await OllamaTextClassifier(settings, client).classify(reply_tweet())


async def test_classifier_repairs_missing_tags(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    missing_tags = json.dumps(
        {
            "relevant": False,
            "importance": 1,
            "topic": "meme",
            "reason": "A joke with no practical product information.",
            "summary": "A reset-related joke.",
        }
    )
    repaired = json.dumps(
        {
            "relevant": False,
            "importance": 1,
            "topic": "meme",
            "tags": ["meme", "reset"],
            "reason": "A joke with no practical product information.",
            "summary": "A reset-related joke.",
        }
    )
    client = FakeOllamaClient([missing_tags, repaired])

    result, _raw = await OllamaTextClassifier(settings, client).classify(reply_tweet())

    assert result.tags == ["meme", "reset"]
    assert len(client.calls) == 2


async def test_classifier_selectively_verifies_high_risk_reply(tmp_path) -> None:
    settings = load_settings(config_path=tmp_path / "missing.yaml")
    first = json.dumps(
        {
            "relevant": True,
            "importance": 9,
            "topic": "Competitor limits",
            "tags": ["limits", "codex"],
            "tone": "literal",
            "stance": "supportive",
            "reason": "The parent discusses limits.",
            "summary": "The reply confirms the parent announcement.",
        }
    )
    corrected = json.dumps(
        {
            "relevant": False,
            "importance": 2,
            "topic": "Routine conversation",
            "tags": ["conversation", "other"],
            "tone": "sarcastic",
            "stance": "uncertain",
            "reason": "The monitored reply is a short ambiguous reaction and adds no concrete product information.",
            "summary": "The reply is a brief reaction to the surrounding discussion without a concrete announcement.",
        }
    )
    client = FakeOllamaClient([first, corrected])
    classifier = OllamaTextClassifier(settings, client)

    result, _raw = await classifier.classify(reply_tweet(), verify=True)

    assert result.importance == 2
    assert result.tone == "sarcastic"
    assert len(client.calls) == 2
    assert classifier.last_trace.verification_used is True
    assert classifier.last_trace.verification_reason == "short relationship post"
