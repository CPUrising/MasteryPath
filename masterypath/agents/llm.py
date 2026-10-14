"""LLM client abstraction (ADR-014).

The domain layer never imports a provider SDK. The loop depends only on
``LLMClient``; tests use :class:`FakeLLMClient` (offline). The real provider is
wired here and is the only place that would import an SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


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

    Real implementation (native function calling + streaming) lands when the
    provider is wired at M2 runtime; it must not leak provider types upward.
    """

    def __init__(self, *, api_key: str | None = None, model: str = "deepseek-chat") -> None:
        self.api_key = api_key
        self.model = model

    def chat(self, messages: list[dict[str, Any]], tools: list[str]) -> LLMResponse:
        raise NotImplementedError(
            "DeepSeekClient is not wired yet; provide DEEPSEEK_API_KEY and the "
            "native tool-calling adapter before using it."
        )


__all__ = ["DeepSeekClient", "FakeLLMClient", "LLMClient", "LLMResponse", "ToolCall"]
