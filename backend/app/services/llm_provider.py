"""LLM provider abstraction. Production uses Groq; there is NO fake-answer fallback here.

A deterministic mock for tests lives in app/tests/mocks.py, never in this module.
"""
import logging
from typing import Protocol

import httpx

log = logging.getLogger(__name__)

# Reasoning models spend hidden "thinking" tokens out of the same output budget as the visible answer.
# Without headroom a short max_tokens can be used up before any answer text is produced.
REASONING_HEADROOM_TOKENS = 2000


class LLMNotConfigured(Exception):
    """No API key is configured."""


class LLMError(Exception):
    """The provider call failed. The message is safe to show to users."""


class LLMProvider(Protocol):
    provider: str
    model: str

    @property
    def configured(self) -> bool: ...

    def generate(self, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.1, max_tokens: int = 1200) -> str: ...


class UnconfiguredLLM:
    provider = "groq"

    def __init__(self, model: str):
        self.model = model

    @property
    def configured(self) -> bool:
        return False

    def generate(self, *args, **kwargs) -> str:
        raise LLMNotConfigured("GROQ_API_KEY is not set. Add it to backend/.env and restart the backend.")


def _error_code(resp: httpx.Response) -> str:
    """Groq's machine-readable error code (e.g. 'model_decommissioned'). Never the whole body, which could echo input."""
    try:
        return str(resp.json().get("error", {}).get("code") or "")
    except Exception:
        return ""


class GroqProvider:
    """Groq exposes an OpenAI-compatible chat-completions endpoint."""

    provider = "groq"

    def __init__(self, api_key: str, model: str, base_url: str, timeout: int, reasoning_effort: str | None = None):
        self._key = api_key
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._timeout = timeout
        self._is_reasoning = "gpt-oss" in model.lower()
        self._effort = reasoning_effort if self._is_reasoning else None

    @property
    def configured(self) -> bool:
        return True

    def _payload(self, system: str, user: str, json_mode: bool, temperature: float, max_tokens: int) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_completion_tokens": max_tokens + (REASONING_HEADROOM_TOKENS if self._is_reasoning else 0),
        }
        if self._effort:
            payload["reasoning_effort"] = self._effort
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def generate(self, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.1, max_tokens: int = 1200) -> str:
        payload = self._payload(system, user, json_mode, temperature, max_tokens)
        try:
            resp = httpx.post(self._url, json=payload, headers={"Authorization": f"Bearer {self._key}"}, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise LLMError("The language model timed out. Try again.") from exc
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach the Groq API. Check your internet connection.") from exc
        if resp.status_code == 401:
            raise LLMError("Groq rejected the API key (401). Check GROQ_API_KEY in backend/.env.")
        if resp.status_code == 429:
            raise LLMError("Groq rate limit reached (429). Wait a moment and try again.")
        if resp.status_code >= 400:
            code = _error_code(resp)
            log.warning("Groq returned HTTP %s (%s)", resp.status_code, code or "no code")  # body deliberately not logged
            if resp.status_code == 404 or code in {"model_decommissioned", "model_not_found"}:
                raise LLMError(
                    f"Groq does not offer the model '{self.model}' (it may have been retired). "
                    "Set GROQ_MODEL in backend/.env to a current model, for example openai/gpt-oss-120b, "
                    "and restart the backend. See https://console.groq.com/docs/models"
                )
            raise LLMError(f"Groq returned an error (HTTP {resp.status_code}). Check the model name in GROQ_MODEL.")
        try:
            choice = resp.json()["choices"][0]
            content = (choice["message"].get("content") or "").strip()
        except (KeyError, IndexError, ValueError, AttributeError) as exc:
            raise LLMError("Groq returned an unexpected response.") from exc
        if not content:
            if choice.get("finish_reason") == "length":
                raise LLMError("The model ran out of output tokens before it wrote an answer. Try again, or set GROQ_REASONING_EFFORT=low.")
            raise LLMError("The model returned an empty response. Try again.")
        return content
