"""LLM client abstraction (ADR-014).

The domain layer never imports a provider SDK. The loop depends only on
``LLMClient``; tests use :class:`FakeLLMClient` (offline). Real providers talk
HTTP here and are the only place that would import an SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Iterator, Protocol

import httpx


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    def chat(
        self, messages: list[dict[str, Any]], tools: list[str]
    ) -> LLMResponse: ...


class FakeLLMClient:
    """Scripted client: returns pre-canned responses in order (offline tests)."""

    def __init__(self, script: list[LLMResponse]) -> None:
        self._script = list(script)
        self.calls: list[list[dict[str, Any]]] = []

    def chat(self, messages: list[dict[str, Any]], tools: list[str]) -> LLMResponse:
        self.calls.append(list(messages))
        if not self._script:
            return LLMResponse(text="(no more scripted responses)")
        return self._script.pop(0)


class DeepSeekClient:
    """Adapter placeholder for the DeepSeek provider.

    Kept for backwards compatibility; new code uses
    :class:`OpenAICompatibleClient` built from the settings store.
    """

    def __init__(self, *, api_key: str | None = None, model: str = "deepseek-chat") -> None:
        self.api_key = api_key
        self.model = model

    def chat(self, messages: list[dict[str, Any]], tools: list[str]) -> LLMResponse:
        return OpenAICompatibleClient(
            base_url="https://api.deepseek.com",
            api_key=self.api_key or "",
            model=self.model,
        ).chat(messages, tools)


class LLMError(RuntimeError):
    """A provider call failed; the message is safe to show to the learner."""


def _chat_endpoint(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat client (chat + streaming).

    Works with OpenAI, DeepSeek and Ollama's OpenAI-compatible endpoint. The
    API key never leaves this object; upstream bodies are not echoed.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        model: str,
        protocol: str = "openai",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or "").strip()
        self.api_key = api_key or ""
        self.model = model
        self.protocol = (protocol or "openai").lower()
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        key = self.api_key.strip()
        if key:
            headers["authorization"] = f"Bearer {key}"
        return headers

    def _require_config(self) -> None:
        if self.protocol == "anthropic":
            raise LLMError("Anthropic chat is not supported yet; choose another protocol.")
        if not self.base_url or not self.model:
            raise LLMError("No chat model is configured. Add one under Settings → Language models.")

    def chat(self, messages: list[dict[str, Any]], tools: list[str] | None = None) -> LLMResponse:
        self._require_config()
        body: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False}
        try:
            response = httpx.post(
                _chat_endpoint(self.base_url),
                headers=self._headers(),
                json=body,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMError("The model provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach the model provider.") from exc
        if response.status_code != 200:
            raise LLMError(f"The model provider returned HTTP {response.status_code}.")
        try:
            payload = response.json()
            content = payload["choices"][0]["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("The model provider returned an unexpected payload.") from exc
        return LLMResponse(text=str(content))

    def stream_chat(self, messages: list[dict[str, Any]]) -> Iterator[str]:
        """Yield text deltas from a streaming chat completion."""
        self._require_config()
        body: dict[str, Any] = {"model": self.model, "messages": messages, "stream": True}
        try:
            with httpx.stream(
                "POST",
                _chat_endpoint(self.base_url),
                headers=self._headers(),
                json=body,
                timeout=self.timeout,
            ) as response:
                if response.status_code != 200:
                    raise LLMError(
                        f"The model provider returned HTTP {response.status_code}."
                    )
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        return
                    try:
                        payload = json.loads(data)
                        delta = payload["choices"][0]["delta"].get("content")
                    except (ValueError, KeyError, IndexError, TypeError):
                        continue
                    if delta:
                        yield str(delta)
        except httpx.TimeoutException as exc:
            raise LLMError("The model provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach the model provider.") from exc


__all__ = [
    "DeepSeekClient",
    "FakeLLMClient",
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "OpenAICompatibleClient",
    "ToolCall",
]
