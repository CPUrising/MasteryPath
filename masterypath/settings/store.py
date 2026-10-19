"""Settings / configuration store (JSON per workspace).

Mirrors DeepTutor's `data/user/settings/*.json` in spirit: a small JSON document
holding providers, language models, the task model, embedding, and general
preferences. No secrets are logged.
"""

from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any

_DEFAULTS: dict[str, Any] = {
    "providers": [],
    # Model pages are lists with one active entry (DeepTutor parity).
    "llm": {"models": [], "active_id": ""},
    "task-models": {"models": [], "active_id": ""},
    "embedding": {"models": [], "active_id": ""},
    "general": {"interface_language": "zh", "response_language": "zh"},
    # Defaults for how knowledge-base documents are chunked (token units).
    "indexing": {"chunk_size": 512, "chunk_overlap": 64},
}

#: Sections shaped as ``{models: [...], active_id: ""}``.
MODEL_SECTIONS: tuple[str, ...] = ("llm", "task-models", "embedding")

#: Protocols a provider can speak. ``openai`` covers every OpenAI-compatible
#: endpoint (the common case); ``anthropic`` and ``ollama`` get their own auth
#: and discovery paths; ``custom`` keeps whatever the user typed.
PROVIDER_PROTOCOLS: tuple[str, ...] = ("openai", "anthropic", "ollama", "custom")

SECTIONS: tuple[str, ...] = tuple(_DEFAULTS)


def _normalize_provider(value: Any) -> Any:
    """Coerce one provider entry, defaulting ``protocol`` and dropping junk detection.

    ``detection`` is a cache of the last probe result. It is kept verbatim so a
    load/edit/save round trip preserves it, but anything that is not a dict is
    discarded rather than served to the UI.
    """
    if not isinstance(value, dict):
        return value
    provider = dict(value)
    protocol = str(provider.get("protocol") or "").strip().lower()
    provider["protocol"] = protocol if protocol in PROVIDER_PROTOCOLS else "openai"
    detection = provider.get("detection")
    if not isinstance(detection, dict):
        provider.pop("detection", None)
    return provider


def _normalize_providers(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return [_normalize_provider(item) for item in value]


def _normalize_model_entry(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    entry = dict(value)
    services = entry.get("services")
    if isinstance(services, list):
        entry["services"] = [str(item) for item in services if item]
    else:
        entry.pop("services", None)
    return entry


def default_settings() -> dict[str, Any]:
    return json.loads(json.dumps(_DEFAULTS))


def _normalize_model_section(value: Any) -> dict[str, Any]:
    """Coerce a stored model section to ``{models: [...], active_id: str}``.

    Older payloads stored a single ``{provider_id, model}``; that is folded into
    a one-entry list so an upgrade keeps whatever was configured.
    """
    if not isinstance(value, dict):
        return {"models": [], "active_id": ""}
    models = value.get("models")
    if not isinstance(models, list):
        models = []
        legacy_model = str(value.get("model") or "").strip()
        if legacy_model:
            models = [
                {
                    "id": "m1",
                    "provider_id": str(value.get("provider_id") or value.get("provider") or ""),
                    "model": legacy_model,
                    "name": legacy_model,
                }
            ]
    return {
        "models": [_normalize_model_entry(item) for item in models],
        "active_id": str(value.get("active_id") or ""),
    }


class UnknownSection(KeyError):
    pass


class SettingsStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "settings.json"
        self._lock = threading.RLock()

    def read(self) -> dict[str, Any]:
        with self._lock:
            merged = default_settings()
            if self.path.exists():
                try:
                    data = json.loads(self.path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    data = {}
                for key, value in data.items():
                    if isinstance(value, dict) and isinstance(merged.get(key), dict):
                        merged[key].update(value)
                    else:
                        merged[key] = value
            for name in MODEL_SECTIONS:
                merged[name] = _normalize_model_section(merged[name])
            merged["providers"] = _normalize_providers(merged.get("providers"))
            return merged

    def section(self, name: str) -> Any:
        if name not in _DEFAULTS:
            raise UnknownSection(name)
        return self.read()[name]

    def write_section(self, name: str, value: Any) -> Any:
        if name not in _DEFAULTS:
            raise UnknownSection(name)
        if name in MODEL_SECTIONS:
            value = _normalize_model_section(value)
        elif name == "providers":
            value = _normalize_providers(value)
        with self._lock:
            data = self.read()
            data[name] = value
            self.path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return data[name]


__all__ = ["SECTIONS", "SettingsStore", "UnknownSection", "default_settings"]
