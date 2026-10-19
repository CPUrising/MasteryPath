"""Model resolution: provider_id disambiguates, missing config is a clear error."""

from __future__ import annotations

import pytest

from masterypath.agents.llm import LLMError
from masterypath.agents.model_resolution import resolve_llm_config
from masterypath.settings.store import SettingsStore


@pytest.fixture()
def settings(tmp_path):
    store = SettingsStore(tmp_path)
    store.write_section(
        "providers",
        [
            {"id": "pa", "name": "A", "base_url": "https://a.example/v1", "api_key": "ka", "protocol": "openai"},
            {"id": "pb", "name": "B", "base_url": "https://b.example/v1", "api_key": "kb", "protocol": "ollama"},
        ],
    )
    store.write_section(
        "llm",
        {
            "models": [
                {"id": "shared", "provider_id": "pa", "model": "same-name", "name": "A model"},
                {"id": "shared-b", "provider_id": "pb", "model": "same-name", "name": "B model"},
            ],
            "active_id": "shared",
        },
    )
    return store


def test_default_uses_active_model(settings):
    config = resolve_llm_config(settings)
    assert config["model_id"] == "shared"
    assert config["base_url"] == "https://a.example/v1"
    assert config["protocol"] == "openai"


def test_provider_id_disambiguates_same_model_name(settings):
    config = resolve_llm_config(
        settings, {"provider_id": "pb", "model_id": "shared-b"}
    )
    assert config["base_url"] == "https://b.example/v1"
    assert config["protocol"] == "ollama"


def test_unknown_selection_errors(settings):
    with pytest.raises(LLMError) as excinfo:
        resolve_llm_config(settings, {"provider_id": "pb", "model_id": "nope"})
    assert excinfo.value.code == "bad_request"


def test_no_models_configured(tmp_path):
    store = SettingsStore(tmp_path)
    with pytest.raises(LLMError) as excinfo:
        resolve_llm_config(store)
    assert "No language model" in str(excinfo.value)
