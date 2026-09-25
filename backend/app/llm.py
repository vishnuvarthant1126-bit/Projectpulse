"""Answer-model providers. Both return the model's raw JSON text for a system prompt,
user prompt and JSON schema. API keys are read from server-side settings only."""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from .config import Settings


class LLMError(Exception):
    pass


class LLM(Protocol):
    name: str

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> str: ...


class AnthropicLLM:
    """Claude Messages API with JSON-schema structured output (output_config.format)."""

    def __init__(self, s: Settings):
        self.name = s.llm_model
        self.s = s
        self.url = (s.llm_base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages"
        self.headers = {
            "x-api-key": s.llm_api_key.get_secret_value() if s.llm_api_key else "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
        body = {
            "model": self.s.llm_model,
            "max_tokens": self.s.llm_max_tokens,
            "temperature": self.s.llm_temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
        }
        try:
            r = httpx.post(self.url, headers=self.headers, json=body, timeout=self.s.llm_timeout_s)
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach the answer model: {type(exc).__name__}") from exc
        if r.status_code >= 400:
            raise LLMError(f"Answer model returned HTTP {r.status_code}")
        data = r.json()
        if data.get("stop_reason") == "refusal":
            raise LLMError("The answer model declined to answer this request.")
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


class OpenAICompatibleLLM:
    """OpenAI Chat Completions or any compatible server (vLLM, Ollama, LM Studio...)."""

    def __init__(self, s: Settings):
        self.name = s.llm_model
        self.s = s
        self.url = (s.llm_base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        self.headers = {"Authorization": f"Bearer {s.llm_api_key.get_secret_value() if s.llm_api_key else ''}"}

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
        """Ask for strict JSON-schema output first. Some compatible servers (e.g. Gemini's
        OpenAI endpoint, older vLLM/Ollama builds) reject parts of that request with HTTP 400,
        so fall back to plain JSON mode with the schema in the prompt, then to no
        response_format at all. The backend validates the result either way."""
        schema_hint = "\n\nReturn only a JSON object that matches this JSON schema:\n" + json.dumps(schema)
        attempts = [
            (system, {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema, "strict": True}}),
            (system + schema_hint, {"type": "json_object"}),
            (system + schema_hint, None),
        ]
        last_status = None
        for sys_prompt, response_format in attempts:
            body: dict[str, Any] = {
                "model": self.s.llm_model,
                "temperature": self.s.llm_temperature,
                "max_tokens": self.s.llm_max_tokens,
                "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}],
            }
            if response_format:
                body["response_format"] = response_format
            try:
                r = httpx.post(self.url, headers=self.headers, json=body, timeout=self.s.llm_timeout_s)
            except httpx.HTTPError as exc:
                raise LLMError(f"Could not reach the answer model: {type(exc).__name__}") from exc
            if r.status_code == 400:
                last_status = 400
                continue  # try a simpler output mode
            if r.status_code == 429:
                raise LLMError("The answer model is busy (rate limit reached). Please try again in a minute.")
            if r.status_code >= 400:
                raise LLMError(f"Answer model returned HTTP {r.status_code}")
            data = r.json()
            if isinstance(data, list):  # some gateways wrap the response in a list
                data = data[0]
            msg = data["choices"][0]["message"]
            if msg.get("refusal"):
                raise LLMError("The answer model declined to answer this request.")
            return msg.get("content") or ""
        raise LLMError(f"Answer model returned HTTP {last_status}")


def build_llm(s: Settings) -> LLM | None:
    if not s.llm_enabled:
        return None
    if s.llm_provider == "anthropic":
        return AnthropicLLM(s)
    if s.llm_provider == "openai":
        return OpenAICompatibleLLM(s)
    return None


def parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise LLMError("The answer model did not return JSON.")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError("The answer model returned malformed JSON.") from exc
