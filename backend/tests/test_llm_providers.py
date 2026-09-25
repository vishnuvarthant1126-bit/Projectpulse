"""OpenAI-compatible provider (used for OpenAI, Gemini, vLLM, Ollama): output-mode fallbacks
and error handling, tested with a fake HTTP layer (no network, no keys)."""

import json

import httpx
import pytest

from app.config import Settings
from app.llm import LLMError, OpenAICompatibleLLM, build_llm, parse_json


class FakeResponse:
    def __init__(self, status: int, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def ok(content: str):
    return FakeResponse(200, {"choices": [{"message": {"content": content}}]})


@pytest.fixture
def gemini_settings():
    return Settings(
        llm_provider="openai",
        llm_model="gemini-3.8-flash",
        llm_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        llm_api_key="test-key",
        _env_file=None,
    )


def test_build_llm_uses_compatible_base_url(gemini_settings):
    llm = build_llm(gemini_settings)
    assert isinstance(llm, OpenAICompatibleLLM)
    assert llm.url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert llm.headers["Authorization"] == "Bearer test-key"


def test_falls_back_to_json_mode_when_schema_mode_rejected(gemini_settings, monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):  # noqa: A002
        calls.append(json)
        if json.get("response_format", {}).get("type") == "json_schema":
            return FakeResponse(400, {"error": "unsupported"})
        return ok('```json\n{"answer_type": "answer", "summary": "ok [S1]"}\n```')

    monkeypatch.setattr(httpx, "post", fake_post)
    out = OpenAICompatibleLLM(gemini_settings).complete_json("sys", "user", {"type": "object"})
    assert parse_json(out)["summary"] == "ok [S1]"
    assert [c.get("response_format", {}).get("type") for c in calls] == ["json_schema", "json_object"]
    assert "matches this JSON schema" in calls[1]["messages"][0]["content"]


def test_last_resort_without_response_format(gemini_settings, monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):  # noqa: A002
        calls.append(json)
        return FakeResponse(400) if "response_format" in json else ok(json_dumps({"answer_type": "answer"}))

    json_dumps = json.dumps
    monkeypatch.setattr(httpx, "post", fake_post)
    out = OpenAICompatibleLLM(gemini_settings).complete_json("sys", "user", {"type": "object"})
    assert parse_json(out) == {"answer_type": "answer"}
    assert len(calls) == 3


def test_rate_limit_and_auth_errors_are_readable(gemini_settings, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(429))
    with pytest.raises(LLMError, match="busy"):
        OpenAICompatibleLLM(gemini_settings).complete_json("s", "u", {})
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(401))
    with pytest.raises(LLMError, match="HTTP 401"):
        OpenAICompatibleLLM(gemini_settings).complete_json("s", "u", {})


def test_server_errors_fall_back_then_report_unavailable(gemini_settings, monkeypatch):
    monkeypatch.setattr("app.llm.time.sleep", lambda s: None)
    calls = []

    def fake_post(url, headers, json, timeout):  # noqa: A002
        calls.append(json.get("response_format", {}).get("type"))
        if calls[-1] == "json_schema":
            return FakeResponse(503, {"error": {"message": "The model is overloaded."}})
        return ok('{"answer_type": "answer"}')

    monkeypatch.setattr(httpx, "post", fake_post)
    assert parse_json(OpenAICompatibleLLM(gemini_settings).complete_json("s", "u", {})) == {"answer_type": "answer"}
    assert calls == ["json_schema", "json_object"]

    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(503, [{"error": {"message": "overloaded"}}]))
    with pytest.raises(LLMError, match="temporarily unavailable"):
        OpenAICompatibleLLM(gemini_settings).complete_json("s", "u", {})


def test_gemini_gets_low_reasoning_effort_and_empty_content_is_explained(gemini_settings, monkeypatch):
    bodies = []

    def fake_post(url, headers, json, timeout):  # noqa: A002
        bodies.append(json)
        return FakeResponse(200, {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(LLMError, match="ran out of output tokens"):
        OpenAICompatibleLLM(gemini_settings).complete_json("s", "u", {})
    assert bodies[0]["reasoning_effort"] == "low" and bodies[0]["max_tokens"] == 8192


def test_reasoning_effort_not_sent_to_other_servers(monkeypatch):
    s = Settings(llm_provider="openai", llm_model="gpt-x", llm_api_key="k", _env_file=None)
    bodies = []
    monkeypatch.setattr(httpx, "post", lambda url, headers, json, timeout: bodies.append(json) or ok("{}"))
    OpenAICompatibleLLM(s).complete_json("s", "u", {})
    assert "reasoning_effort" not in bodies[0]
