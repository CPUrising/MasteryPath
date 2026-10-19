"""Provider detection — probe, model fetch, dimension, and settings wiring."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from masterypath.api.app import create_app
from masterypath.learning.storage import LearningStore
from masterypath.settings import providers as probe


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="")


def test_valid_base_url():
    assert probe.valid_base_url("https://api.example.com/v1")
    assert probe.valid_base_url("http://127.0.0.1:11434/v1")
    assert not probe.valid_base_url("ftp://api.example.com")
    assert not probe.valid_base_url("https://user:pass@api.example.com")
    assert not probe.valid_base_url("not a url")
    assert not probe.valid_base_url("")


def test_classify_model():
    assert probe.classify_model("gpt-4o-mini") == "llm"
    assert probe.classify_model("deepseek-chat") == "llm"
    assert probe.classify_model("text-embedding-3-small") == "embedding"
    assert probe.classify_model("bge-m3") == "embedding"
    assert probe.classify_model("whisper-1") == ""
    assert probe.classify_model("dall-e-3") == ""


def test_probe_connected_and_classifies():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        assert request.headers.get("authorization") == "Bearer sk-secret"
        return httpx.Response(
            200,
            json={"data": [{"id": "gpt-4o"}, {"id": "text-embedding-3-small"}]},
        )

    with _client(handler) as client:
        result = probe.probe_provider(
            "openai", "https://api.example.com/v1", "sk-secret", client=client
        )
    assert result["status"] == "connected"
    assert {item["id"]: item["services"] for item in result["models"]} == {
        "gpt-4o": ["llm"],
        "text-embedding-3-small": ["embedding"],
    }
    assert "sk-secret" not in str(result)


def test_probe_filters_by_service():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": [{"id": "gpt-4o"}, {"id": "bge-m3"}]}
        )

    with _client(handler) as client:
        embedding = probe.fetch_models(
            "openai", "https://api.example.com/v1", "k", service="embedding", client=client
        )
    assert [item["id"] for item in embedding["models"]] == ["bge-m3"]


def test_probe_status_vocabulary():
    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    with _client(unauthorized) as client:
        assert probe.probe_provider("openai", "https://x.example.com", "k", client=client)[
            "status"
        ] == "auth_error"

    def missing(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with _client(missing) as client:
        assert probe.probe_provider("openai", "https://x.example.com", "k", client=client)[
            "status"
        ] == "unavailable"

    def timed_out(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    with _client(timed_out) as client:
        assert probe.probe_provider("openai", "https://x.example.com", "k", client=client)[
            "status"
        ] == "timeout"


def test_probe_invalid_url_and_anthropic():
    assert probe.probe_provider("openai", "javascript:alert(1)")["status"] == "invalid_url"
    assert probe.probe_provider("anthropic", "https://api.anthropic.com")["status"] == (
        "unavailable"
    )


def test_ollama_discovery_path():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"models": [{"name": "llama3:latest"}]})

    with _client(handler) as client:
        result = probe.probe_provider(
            "ollama", "http://127.0.0.1:11434/v1", "", client=client
        )
    assert seen == ["/api/tags"]
    assert result["models"][0]["id"] == "llama3:latest"


def test_detect_dimension():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/embeddings")
        return httpx.Response(200, json={"data": [{"embedding": [0.0] * 1536}]})

    with _client(handler) as client:
        result = probe.detect_dimension(
            "openai", "https://api.example.com/v1", "k", "text-embedding-3-small", client=client
        )
    assert result == {"status": "connected", "dimension": 1536}


def test_detect_dimension_unavailable():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with _client(handler) as client:
        result = probe.detect_dimension(
            "openai", "https://api.example.com/v1", "k", "m", client=client
        )
    assert result == {"status": "unavailable", "dimension": 0}


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(tmp_path)
    app = create_app(store)
    with TestClient(app) as client:
        yield client
    store.close()


def test_provider_catalog_endpoint(env):
    catalog = env.get("/settings/providers/catalog").json()
    ids = {item["id"] for item in catalog}
    assert {"deepseek", "openai", "ollama", "custom"} <= ids


def test_provider_protocol_default_and_back_compat(env):
    providers = [
        {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com", "api_key": "sk"}
    ]
    saved = env.put("/settings/providers", json=providers).json()
    assert saved[0]["protocol"] == "openai"
    assert env.get("/settings/providers").json()[0]["protocol"] == "openai"
    # A model section keeps / normalizes the detection service tags.
    section = {
        "models": [
            {"id": "m1", "provider_id": "deepseek", "model": "deepseek-chat", "name": "Chat", "services": ["llm"]}
        ],
        "active_id": "m1",
    }
    assert env.put("/settings/llm", json=section).json() == section


def test_probe_endpoint_uses_saved_credentials(env, monkeypatch):
    env.put(
        "/settings/providers",
        json=[
            {
                "id": "p1",
                "name": "Local",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-saved",
                "protocol": "ollama",
            }
        ],
    )
    captured: dict = {}

    def fake(protocol, base_url, api_key=None, *, service="", client=None):
        captured.update(protocol=protocol, base_url=base_url, api_key=api_key, service=service)
        return {"status": "connected", "models": [{"id": "m", "services": ["llm"]}]}

    monkeypatch.setattr(probe, "probe_provider", fake)
    result = env.post("/settings/providers/probe", json={"provider_id": "p1", "service": "llm"}).json()
    assert result["status"] == "connected"
    assert captured == {
        "protocol": "ollama",
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-saved",
        "service": "llm",
    }
