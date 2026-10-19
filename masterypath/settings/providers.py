"""Provider connectivity and model discovery (read-only).

Three operations the settings UI needs, ported in spirit from DeepTutor's
``provider_probe``:

* :func:`probe_provider` — verify credentials and list the provider's models.
* :func:`fetch_models` — the model list alone (the "auto detect" picker).
* :func:`detect_dimension` — one tiny embedding request, to learn a model's
  vector width.

Nothing here writes configuration or logs credentials. Failures are reported as
a small status vocabulary rather than upstream exception text, which can carry
the API key or URL. Every function accepts an optional ``httpx.Client`` so tests
can drive it through ``httpx.MockTransport`` with no network.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx

DEFAULT_TIMEOUT = 20.0

#: Inference-endpoint suffixes stripped before discovery, so a base_url that
#: already points at `/chat/completions` still discovers from the API root.
_INFERENCE_SUFFIXES = (
    "/embeddings",
    "/chat/completions",
    "/responses",
    "/messages",
    "/completions",
    "/api/embed",
    "/api/embeddings",
)

_EMBEDDING_HINTS = (
    "embed",
    "bge-",
    "gte-",
    "e5-",
    "voyage",
    "nomic",
    "text-similarity",
)
#: Non-text endpoints that would otherwise be miscounted as chat models.
_EXCLUDED_HINTS = (
    "whisper",
    "tts",
    "dall-e",
    "image",
    "video",
    "rerank",
    "moderation",
    "audio",
    "speech",
    "transcribe",
)


def _default_client() -> httpx.Client:
    return httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=False)


def _use_client(client: httpx.Client | None) -> tuple[httpx.Client, bool]:
    """Return ``(client, owned)``; only an owned client is closed by the caller."""
    return (client, False) if client is not None else (_default_client(), True)


def _split_base_url(base_url: str) -> str:
    text = (base_url or "").strip().rstrip("/")
    for suffix in _INFERENCE_SUFFIXES:
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def valid_base_url(base_url: str) -> bool:
    try:
        parsed = urlsplit((base_url or "").strip())
        # Accessing ``.port`` validates malformed/non-numeric ports.
        parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.hostname)
        and not parsed.username
        and not parsed.password
    )


def _discovery_request(protocol: str, base_url: str) -> str:
    parsed = urlsplit(_split_base_url(base_url))
    path = parsed.path.rstrip("/")
    if protocol == "ollama":
        if path.endswith("/v1"):
            path = path[: -len("/v1")]
        path += "/api/tags"
    else:
        path += "/models"
    return urlunsplit(parsed._replace(path=path, query="", fragment=""))


def _auth_headers(protocol: str, api_key: str | None) -> dict[str, str]:
    key = (api_key or "").strip()
    if not key:
        return {}
    if protocol == "anthropic":
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    if protocol == "ollama":
        return {}
    return {"Authorization": f"Bearer {key}"}


def _model_items(payload: Any) -> list | None:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "models"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return None


def _model_id(item: Any) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""
    for key in ("id", "model", "name"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def classify_model(model_id: str) -> str:
    """Return ``"embedding"`` or ``"llm"`` for one model id.

    Names are the only signal an OpenAI-compatible listing reliably carries, so
    this is deliberately keyword-based; the model editor also lets the user move
    a model to the right page by hand.
    """
    name = (model_id or "").lower()
    if any(hint in name for hint in _EXCLUDED_HINTS):
        return ""
    if any(hint in name for hint in _EMBEDDING_HINTS):
        return "embedding"
    return "llm"


def _classify_items(items: list) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for item in items:
        model_id = _model_id(item)
        if not model_id or model_id in seen:
            continue
        kind = classify_model(model_id)
        if not kind:
            continue
        seen[model_id] = {"id": model_id, "services": [kind]}
    return list(seen.values())


def _status_for_http(status_code: int) -> str:
    if status_code in {401, 403}:
        return "auth_error"
    if status_code in {404, 405, 501}:
        return "unavailable"
    if status_code == 429:
        return "rate_limited"
    return "http_error"


def probe_provider(
    protocol: str,
    base_url: str,
    api_key: str | None = None,
    *,
    service: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Check access and list models, without a billable inference call.

    ``service`` ("llm" | "embedding" | "task") narrows the returned list; an
    unknown or absent value keeps every recognized model. Results are shaped for
    the UI: ``{status, models, http_status?, warning?}``.
    """
    protocol = (protocol or "openai").strip().lower()
    base_url = (base_url or "").strip()
    if protocol == "anthropic":
        return {"status": "unavailable", "models": [], "warning": "manual_entry"}
    if not valid_base_url(base_url):
        return {"status": "invalid_url", "models": []}

    url = _discovery_request(protocol, base_url)
    headers = _auth_headers(protocol, api_key)
    http, owned = _use_client(client)
    try:
        response = http.get(url, headers=headers)
    except httpx.TimeoutException:
        return {"status": "timeout", "models": []}
    except httpx.HTTPError:
        return {"status": "unreachable", "models": []}
    finally:
        if owned:
            http.close()

    if response.status_code != 200:
        return {
            "status": _status_for_http(response.status_code),
            "models": [],
            "http_status": response.status_code,
        }
    try:
        payload = response.json()
    except ValueError:
        return {"status": "unavailable", "models": []}
    items = _model_items(payload)
    if items is None:
        return {"status": "unavailable", "models": []}

    models = _classify_items(items)
    wanted = "llm" if service == "task" else service
    if wanted in {"llm", "embedding"}:
        models = [item for item in models if wanted in item["services"]]
    result: dict[str, Any] = {"status": "connected", "models": models}
    if not models:
        result["warning"] = "no_models"
    return result


def fetch_models(
    protocol: str,
    base_url: str,
    api_key: str | None = None,
    *,
    service: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """The probe's model listing, for the "auto detect" picker."""
    result = probe_provider(
        protocol, base_url, api_key, service=service, client=client
    )
    return {"status": result["status"], "models": result.get("models", [])}


def _embedding_request(protocol: str, base_url: str) -> str:
    parsed = urlsplit(_split_base_url(base_url))
    path = parsed.path.rstrip("/")
    if protocol == "ollama":
        if path.endswith("/v1"):
            path = path[: -len("/v1")]
        path += "/api/embed"
    else:
        path += "/embeddings"
    return urlunsplit(parsed._replace(path=path, query="", fragment=""))


def _dimension_from_payload(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    vectors = payload.get("embeddings")
    if vectors is None:
        data = payload.get("data")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            vectors = [data[0].get("embedding")]
    if not isinstance(vectors, list) or not vectors:
        return 0
    first = vectors[0]
    if isinstance(first, list):
        return len(first)
    return 0


class ProviderError(RuntimeError):
    """A provider call failed; the message is safe to show to the learner."""


def _embeddings_from_payload(payload: Any) -> list[list[float]]:
    if not isinstance(payload, dict):
        raise ProviderError("The embedding endpoint returned an unexpected payload.")
    vectors = payload.get("embeddings")
    if vectors is None:
        data = payload.get("data")
        if isinstance(data, list):
            vectors = [
                item.get("embedding") if isinstance(item, dict) else None
                for item in data
            ]
    if not isinstance(vectors, list):
        raise ProviderError("The embedding endpoint returned no vectors.")
    out: list[list[float]] = []
    for vector in vectors:
        if not isinstance(vector, list) or not vector:
            raise ProviderError("The embedding endpoint returned an empty vector.")
        out.append([float(value) for value in vector])
    return out


def embed_texts(
    protocol: str,
    base_url: str,
    api_key: str | None,
    model: str,
    texts: list[str],
    *,
    client: httpx.Client | None = None,
) -> list[list[float]]:
    """Embed one batch of texts through the configured provider.

    Supports OpenAI-compatible ``/embeddings`` endpoints and Ollama's
    ``/api/embed``. Raises :class:`ProviderError` with a safe message; upstream
    bodies are never echoed because they can contain credentials.
    """
    protocol = (protocol or "openai").strip().lower()
    base_url = (base_url or "").strip()
    model = (model or "").strip()
    if not texts:
        return []
    if not model or not valid_base_url(base_url):
        raise ProviderError("The embedding provider is not configured.")
    if protocol == "anthropic":
        raise ProviderError("Anthropic does not expose an embeddings endpoint.")

    url = _embedding_request(protocol, base_url)
    headers = _auth_headers(protocol, api_key)
    body = {"model": model, "input": texts}
    http, owned = _use_client(client)
    try:
        response = http.post(url, headers=headers, json=body, timeout=60.0)
    except httpx.TimeoutException as exc:
        raise ProviderError("The embedding request timed out.") from exc
    except httpx.HTTPError as exc:
        raise ProviderError("Could not reach the embedding provider.") from exc
    finally:
        if owned:
            http.close()

    if response.status_code != 200:
        raise ProviderError(
            f"The embedding provider returned HTTP {response.status_code}."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderError("The embedding provider returned invalid JSON.") from exc
    vectors = _embeddings_from_payload(payload)
    if len(vectors) != len(texts):
        raise ProviderError("The embedding provider returned the wrong vector count.")
    return vectors



def detect_dimension(
    protocol: str,
    base_url: str,
    api_key: str | None,
    model: str,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Send one minimal embedding request to learn a model's vector width.

    This is a (very small) billable call, so it only runs on an explicit user
    action. Unsupported endpoints return ``status: "unavailable"`` and a zero
    dimension, which the UI reads as "enter it manually".
    """
    protocol = (protocol or "openai").strip().lower()
    base_url = (base_url or "").strip()
    model = (model or "").strip()
    if not model or not valid_base_url(base_url):
        return {"status": "invalid_url", "dimension": 0}
    if protocol == "anthropic":
        return {"status": "unavailable", "dimension": 0}

    url = _embedding_request(protocol, base_url)
    headers = _auth_headers(protocol, api_key)
    body = {"model": model, "input": ["dimension probe"]}
    http, owned = _use_client(client)
    try:
        response = http.post(url, headers=headers, json=body)
    except httpx.TimeoutException:
        return {"status": "timeout", "dimension": 0}
    except httpx.HTTPError:
        return {"status": "unreachable", "dimension": 0}
    finally:
        if owned:
            http.close()

    if response.status_code != 200:
        return {
            "status": _status_for_http(response.status_code),
            "dimension": 0,
            "http_status": response.status_code,
        }
    try:
        payload = response.json()
    except ValueError:
        return {"status": "unavailable", "dimension": 0}
    dimension = _dimension_from_payload(payload)
    if dimension <= 0:
        return {"status": "unavailable", "dimension": 0}
    return {"status": "connected", "dimension": dimension}


#: Vendors the Add-provider panel offers. ``services`` is what the vendor is
#: known to provide, used as the default filter when adding models.
PROVIDER_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "protocol": "openai",
        "services": ["llm", "task"],
        "requires_key": True,
        "monogram": "DS",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "protocol": "openai",
        "services": ["llm", "task", "embedding"],
        "requires_key": True,
        "monogram": "OA",
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "protocol": "anthropic",
        "services": ["llm", "task"],
        "requires_key": True,
        "monogram": "AN",
    },
    {
        "id": "azure",
        "name": "Azure OpenAI",
        "base_url": "",
        "protocol": "openai",
        "services": ["llm", "task", "embedding"],
        "requires_key": True,
        "monogram": "AZ",
    },
    {
        "id": "ollama",
        "name": "Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "protocol": "ollama",
        "services": ["llm", "task", "embedding"],
        "requires_key": False,
        "monogram": "OL",
    },
    {
        "id": "custom",
        "name": "Custom",
        "base_url": "",
        "protocol": "custom",
        "services": ["llm", "task", "embedding"],
        "requires_key": True,
        "monogram": "CU",
    },
)


def provider_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in PROVIDER_CATALOG]


ProbeFn = Callable[..., dict[str, Any]]

__all__ = [
    "PROVIDER_CATALOG",
    "ProviderError",
    "classify_model",
    "detect_dimension",
    "embed_texts",
    "fetch_models",
    "probe_provider",
    "provider_catalog",
    "valid_base_url",
]
