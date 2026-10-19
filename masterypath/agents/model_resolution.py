"""One place that turns settings (+ an optional per-session selection) into a
concrete LLM client.

Both the general chat and the mastery tutor resolve their model through here, so
"which model am I talking to" has a single answer. Selections are addressed by
``{provider_id, model_id}`` because a bare ``model_id`` can repeat across
providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from masterypath.agents.llm import LLMError, OpenAICompatibleClient


@dataclass(frozen=True)
class LLMSelection:
    provider_id: str
    model_id: str


def normalize_selection(value: Any) -> LLMSelection | None:
    """Coerce a stored/requested selection; ``None`` when it names no model."""
    if not isinstance(value, dict):
        return None
    model_id = str(value.get("model_id") or "").strip()
    if not model_id:
        return None
    return LLMSelection(
        provider_id=str(value.get("provider_id") or "").strip(), model_id=model_id
    )


def _not_configured(message: str) -> LLMError:
    return LLMError(message, code="bad_request")


def resolve_llm_config(
    settings: Any, selection: LLMSelection | dict[str, Any] | None = None
) -> dict[str, Any]:
    """Resolve ``{provider_id, model_id}`` (or the active default) to a client config."""
    wanted = normalize_selection(selection) if not isinstance(selection, LLMSelection) else selection
    section = settings.section("llm")
    models = section.get("models") if isinstance(section, dict) else []
    models = models if isinstance(models, list) else []

    chosen = None
    if wanted is not None:
        chosen = next(
            (
                item
                for item in models
                if item.get("id") == wanted.model_id
                and (
                    not wanted.provider_id
                    or str(item.get("provider_id") or "") == wanted.provider_id
                )
            ),
            None,
        )
        if chosen is None:
            raise _not_configured(
                "The selected model is no longer configured. Pick another under Settings → Language models."
            )
    if chosen is None:
        active = str(section.get("active_id") or "") if isinstance(section, dict) else ""
        chosen = next((item for item in models if item.get("id") == active), None)
    if chosen is None and models:
        chosen = models[0]
    if not chosen or not str(chosen.get("model") or "").strip():
        raise _not_configured(
            "No language model is configured. Add one under Settings → Language models."
        )

    provider_id = str(chosen.get("provider_id") or "")
    provider = next(
        (
            item
            for item in settings.section("providers")
            if isinstance(item, dict) and item.get("id") == provider_id
        ),
        None,
    )
    if provider is None or not str(provider.get("base_url") or "").strip():
        raise _not_configured(
            "The model's provider is missing a base URL. Check Settings → Providers."
        )
    return {
        "provider_id": provider_id,
        "model_id": str(chosen.get("id") or ""),
        "name": str(chosen.get("name") or chosen.get("model") or ""),
        "model": str(chosen.get("model") or ""),
        "protocol": str(provider.get("protocol") or "openai"),
        "base_url": str(provider.get("base_url") or ""),
        "api_key": provider.get("api_key") or "",
        "extra_headers": provider.get("extra_headers") or {},
    }


def build_client(config: dict[str, Any]) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url=config["base_url"],
        api_key=config.get("api_key") or "",
        model=config["model"],
        protocol=config.get("protocol") or "openai",
        extra_headers=config.get("extra_headers") or None,
        session_key=str(config.get("session_key") or ""),
    )


__all__ = ["LLMSelection", "build_client", "normalize_selection", "resolve_llm_config"]
