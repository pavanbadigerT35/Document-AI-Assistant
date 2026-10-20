"""GroqProvider request/response handling, tested with a fake httpx.post: no network, no API key."""
import httpx
import pytest

from app.core.config import Settings
from app.services import llm_provider
from app.services.llm_provider import GroqProvider, LLMError

KEY = "gsk_test_key_should_never_appear_in_errors"


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def ok(content="Hello", finish="stop"):
    return FakeResponse(200, {"choices": [{"message": {"content": content}, "finish_reason": finish}]})


@pytest.fixture
def sent(monkeypatch):
    """Capture what would be sent to Groq and let each test choose the reply."""
    box = {"reply": ok(), "payloads": []}

    def fake_post(url, json=None, headers=None, timeout=None):
        box["payloads"].append(json)
        box["url"], box["headers"] = url, headers
        return box["reply"]

    monkeypatch.setattr(llm_provider.httpx, "post", fake_post)
    return box


def provider(model="openai/gpt-oss-120b", effort="low"):
    return GroqProvider(KEY, model, "https://api.groq.com/openai/v1/", 30, effort)


def test_default_model_is_not_the_retired_llama():
    s = Settings(_env_file=None)
    assert s.groq_model == "openai/gpt-oss-120b" and "llama-3.3-70b" not in s.groq_model


def test_reasoning_model_gets_effort_and_token_headroom(sent):
    assert provider().generate("sys", "usr", max_tokens=900) == "Hello"
    payload = sent["payloads"][0]
    assert payload["reasoning_effort"] == "low"
    assert payload["max_completion_tokens"] == 900 + llm_provider.REASONING_HEADROOM_TOKENS
    assert "max_tokens" not in payload
    assert sent["url"] == "https://api.groq.com/openai/v1/chat/completions"


def test_non_reasoning_model_gets_neither_effort_nor_headroom(sent):
    provider(model="some-other/chat-model").generate("sys", "usr", max_tokens=500)
    payload = sent["payloads"][0]
    assert "reasoning_effort" not in payload and payload["max_completion_tokens"] == 500


def test_json_mode_sets_response_format(sent):
    provider().generate("sys", "usr", json_mode=True)
    assert sent["payloads"][0]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("status,body", [
    (400, {"error": {"code": "model_decommissioned", "message": "retired"}}),
    (404, {"error": {"message": "does not exist"}}),
])
def test_retired_model_gives_actionable_message(sent, status, body):
    sent["reply"] = FakeResponse(status, body)
    with pytest.raises(LLMError) as exc:
        provider(model="llama-3.3-70b-versatile").generate("s", "u")
    assert "GROQ_MODEL" in str(exc.value) and "openai/gpt-oss-120b" in str(exc.value) and KEY not in str(exc.value)


def test_auth_and_rate_limit_messages(sent):
    sent["reply"] = FakeResponse(401, {})
    with pytest.raises(LLMError, match="401"):
        provider().generate("s", "u")
    sent["reply"] = FakeResponse(429, {})
    with pytest.raises(LLMError, match="rate limit"):
        provider().generate("s", "u")


def test_empty_answer_is_an_error_not_a_blank_reply(sent):
    sent["reply"] = ok(content="", finish="length")
    with pytest.raises(LLMError, match="ran out of output tokens"):
        provider().generate("s", "u")
    sent["reply"] = ok(content="   ", finish="stop")
    with pytest.raises(LLMError, match="empty response"):
        provider().generate("s", "u")


def test_malformed_response_is_an_error(sent):
    sent["reply"] = FakeResponse(200, {"unexpected": True})
    with pytest.raises(LLMError, match="unexpected response"):
        provider().generate("s", "u")


@pytest.mark.parametrize("exc,text", [(httpx.ReadTimeout("slow"), "timed out"), (httpx.ConnectError("down"), "Could not reach")])
def test_network_failures_are_reported_clearly(monkeypatch, exc, text):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(llm_provider.httpx, "post", boom)
    with pytest.raises(LLMError, match=text) as caught:
        provider().generate("s", "u")
    assert KEY not in str(caught.value)
