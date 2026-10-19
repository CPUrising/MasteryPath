"""LLM client abstraction (ADR-014).

The domain layer never imports a provider SDK. The loop depends only on
``LLMClient``; tests use :class:`FakeLLMClient` (offline). Real providers talk
HTTP here and are the only place that would import an SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Iterator, Protocol
import uuid

import httpx


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    #: True when the provider returned arguments that were not valid JSON; the
    #: loop answers with a failed tool result instead of invoking the tool.
    parse_error: bool = False


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMError(RuntimeError):
    """A provider call failed; the message is safe to show to the learner."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "upstream_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _http_error(status_code: int) -> LLMError:
    """Map an HTTP status to a safe, structured error (never the upstream body)."""
    if status_code in {401, 403}:
        return LLMError(
            "The provider rejected these credentials. Check the API key.",
            code="auth_error",
        )
    if status_code == 404:
        return LLMError(
            "The configured model was not found at this provider.",
            code="model_not_found",
        )
    if status_code == 429:
        return LLMError(
            "The provider is rate limiting requests. Try again later.",
            code="rate_limited",
            retryable=True,
        )
    if status_code == 400:
        return LLMError(
            "The provider rejected the request.", code="bad_request"
        )
    if status_code >= 500:
        return LLMError(
            "The provider returned a server error.", code="upstream_error", retryable=True
        )
    return LLMError(
        f"The model provider returned HTTP {status_code}.", code="upstream_error"
    )


class LLMClient(Protocol):
    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse: ...


class FakeLLMClient:
    """Scripted client: returns pre-canned responses in order (offline tests).

    ``tools_seen`` records the tool definitions passed on each call so tests can
    assert the schema actually reaches the client.
    """

    def __init__(self, script: list[LLMResponse]) -> None:
        self._script = list(script)
        self.calls: list[list[dict[str, Any]]] = []
        self.tools_seen: list[list[dict[str, Any]]] = []

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        self.calls.append(list(messages))
        self.tools_seen.append(list(tools))
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

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        return OpenAICompatibleClient(
            base_url="https://api.deepseek.com",
            api_key=self.api_key or "",
            model=self.model,
        ).chat(messages, tools)



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
        extra_headers: dict[str, str] | None = None,
        session_key: str = "",
    ) -> None:
        self.base_url = (base_url or "").strip()
        self.api_key = api_key or ""
        self.model = model
        self.protocol = (protocol or "openai").lower()
        self.timeout = timeout
        self.extra_headers = dict(extra_headers or {})
        # Some gateways (opencode zen) require a routing session header. Use the
        # conversation key when the caller has one; a per-client uuid otherwise.
        self.session_key = session_key or f"mp-{uuid.uuid4().hex}"

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        key = self.api_key.strip()
        if key:
            headers["authorization"] = f"Bearer {key}"
        headers.update(self.extra_headers)
        host = ""
        try:
            host = httpx.URL(self.base_url).host or ""
        except Exception:  # noqa: BLE001
            host = ""
        if host.endswith("opencode.ai") and "x-opencode-session" not in {
            name.lower() for name in headers
        }:
            headers["x-opencode-session"] = self.session_key
        return headers

    def _require_config(self) -> None:
        if self.protocol == "anthropic":
            raise LLMError("Anthropic chat is not supported yet; choose another protocol.")
        if not self.base_url or not self.model:
            raise LLMError("No chat model is configured. Add one under Settings → Language models.")

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> LLMResponse:
        self._require_config()
        body: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        try:
            response = httpx.post(
                _chat_endpoint(self.base_url),
                headers=self._headers(),
                json=body,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMError(
                "The model provider timed out.", code="upstream_error", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach the model provider.", code="upstream_error") from exc
        if response.status_code != 200:
            raise _http_error(response.status_code)
        try:
            payload = response.json()
            message = payload["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                "The model provider returned an unexpected payload.", code="upstream_error"
            ) from exc

        calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            name = str(function.get("name") or "")
            if not name:
                continue
            raw_arguments = function.get("arguments")
            if isinstance(raw_arguments, dict):
                arguments = raw_arguments
                parse_error = False
            else:
                try:
                    arguments = json.loads(raw_arguments or "{}")
                    parse_error = not isinstance(arguments, dict)
                    if parse_error:
                        arguments = {}
                except (ValueError, TypeError):
                    arguments = {}
                    parse_error = True
            calls.append(
                ToolCall(
                    name=name,
                    arguments=arguments if isinstance(arguments, dict) else {},
                    id=str(raw.get("id") or ""),
                    parse_error=parse_error,
                )
            )
        return LLMResponse(text=str(message.get("content") or ""), tool_calls=calls)

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
                    raise _http_error(response.status_code)
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
            raise LLMError(
                "The model provider timed out.", code="upstream_error", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach the model provider.", code="upstream_error") from exc


__all__ = [
    "DeepSeekClient",
    "FakeLLMClient",
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "OpenAICompatibleClient",
    "ToolCall",
]
