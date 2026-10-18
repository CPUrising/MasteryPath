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
    "llm": {"provider_id": "", "model": ""},
    "task-models": {"provider_id": "", "model": ""},
    "embedding": {"provider": "", "model": "", "dimension": 0},
    "general": {"interface_language": "zh", "response_language": "zh"},
}

SECTIONS: tuple[str, ...] = tuple(_DEFAULTS)


def default_settings() -> dict[str, Any]:
    return json.loads(json.dumps(_DEFAULTS))


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
            return merged

    def section(self, name: str) -> Any:
        if name not in _DEFAULTS:
            raise UnknownSection(name)
        return self.read()[name]

    def write_section(self, name: str, value: Any) -> Any:
        if name not in _DEFAULTS:
            raise UnknownSection(name)
        with self._lock:
            data = self.read()
            data[name] = value
            self.path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return data[name]


__all__ = ["SECTIONS", "SettingsStore", "UnknownSection", "default_settings"]
