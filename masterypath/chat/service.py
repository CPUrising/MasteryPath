"""General chat turns: model resolution, knowledge context, streaming."""

from __future__ import annotations

from typing import Any, Callable, Iterator

from masterypath.agents.llm import LLMError, OpenAICompatibleClient
from masterypath.chat.store import ChatStore, UnknownSession
from masterypath.settings.store import SettingsStore

ClientFactory = Callable[[dict[str, Any]], Any]

_SYSTEM = (
    "You are MasteryPath, a study assistant. Answer the learner directly and "
    "concisely in their language. When reference material is provided below, "
    "ground your answer in it and cite the source file name."
)


def _default_client_factory(config: dict[str, Any]) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url=config["base_url"],
        api_key=config.get("api_key") or "",
        model=config["model"],
        protocol=config.get("protocol") or "openai",
    )


class ChatService:
    def __init__(
        self,
        store: ChatStore,
        settings: SettingsStore,
        *,
        knowledge: Any | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self.knowledge = knowledge
        self._client_factory = client_factory or _default_client_factory

    # -- model resolution --------------------------------------------------
    def resolve_model(self, model_id: str | None = None) -> dict[str, Any]:
        section = self.settings.section("llm")
        models = section.get("models") if isinstance(section, dict) else []
        models = models if isinstance(models, list) else []
        chosen = None
        if model_id:
            chosen = next((m for m in models if m.get("id") == model_id), None)
        if chosen is None:
            active = str(section.get("active_id") or "") if isinstance(section, dict) else ""
            chosen = next((m for m in models if m.get("id") == active), None)
        if chosen is None and models:
            chosen = models[0]
        if not chosen or not str(chosen.get("model") or "").strip():
            raise LLMError(
                "No language model is configured. Add one under Settings → Language models."
            )
        provider_id = str(chosen.get("provider_id") or "")
        provider = next(
            (
                item
                for item in self.settings.section("providers")
                if isinstance(item, dict) and item.get("id") == provider_id
            ),
            None,
        )
        if provider is None or not str(provider.get("base_url") or "").strip():
            raise LLMError(
                "The model's provider is missing a base URL. Check Settings → Providers."
            )
        return {
            "model_id": str(chosen.get("id") or ""),
            "name": str(chosen.get("name") or chosen.get("model") or ""),
            "model": str(chosen.get("model") or ""),
            "provider_id": provider_id,
            "protocol": str(provider.get("protocol") or "openai"),
            "base_url": str(provider.get("base_url") or ""),
            "api_key": provider.get("api_key") or "",
        }

    # -- sessions ----------------------------------------------------------
    def list_sessions(self) -> list[dict[str, Any]]:
        return self.store.list_sessions()

    def create_session(
        self,
        *,
        title: str = "",
        model_id: str = "",
        kb_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.store.create_session(title=title, model_id=model_id, kb_ids=kb_ids or [])

    def session_detail(self, session_id: str) -> dict[str, Any]:
        return {
            "session": self.store.get_session(session_id),
            "messages": self.store.list_messages(session_id),
        }

    def update_session(self, session_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        return self.store.update_session(session_id, fields)

    def delete_session(self, session_id: str) -> None:
        self.store.delete_session(session_id)

    # -- turns -------------------------------------------------------------
    def _knowledge_context(self, kb_ids: list[str], query: str) -> str:
        if not self.knowledge or not kb_ids:
            return ""
        blocks: list[str] = []
        for kb_id in kb_ids:
            try:
                hits = self.knowledge.search(kb_id, query, top_k=4)
            except Exception:  # noqa: BLE001 - retrieval is best-effort context
                hits = []
            if not hits:
                continue
            kb_name = ""
            try:
                kb_name = str(self.knowledge.get(kb_id).get("name") or kb_id)
            except Exception:  # noqa: BLE001
                kb_name = kb_id
            joined = "\n\n".join(
                f"[{hit.get('source') or 'source'}]\n{hit.get('text', '')}" for hit in hits
            )
            blocks.append(f"# {kb_name}\n{joined}")
        if not blocks:
            return ""
        return "Reference material:\n\n" + "\n\n".join(blocks)

    def stream_turn(
        self,
        session_id: str,
        message: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield ``{"type": "delta"|"done"|"error", ...}`` events for one turn."""
        text = (message or "").strip()
        if not text:
            yield {"type": "error", "message": "Type a message first."}
            return
        try:
            session = self.store.get_session(session_id)
        except UnknownSession:
            yield {"type": "error", "message": "This conversation no longer exists."}
            return

        attachment_names = [
            str(item.get("name") or "") for item in (attachments or []) if item.get("name")
        ]
        self.store.add_message(
            session_id,
            "user",
            text,
            [{"name": name} for name in attachment_names],
        )

        if not session.get("title"):
            session = self.store.update_session(
                session_id, {"title": text[:40]}
            )

        history = [
            {"role": item["role"], "content": item["content"]}
            for item in self.store.list_messages(session_id)
            if item["role"] in {"user", "assistant"} and item["content"]
        ]
        context = self._knowledge_context(session.get("kb_ids") or [], text)
        messages: list[dict[str, Any]] = [{"role": "system", "content": _SYSTEM}]
        if context:
            messages.append({"role": "system", "content": context})
        attachment_blocks = []
        for item in attachments or []:
            name = str(item.get("name") or "")
            content = str(item.get("text") or "").strip()
            if name and content:
                attachment_blocks.append(f"[{name}]\n{content[:20000]}")
            elif name:
                attachment_blocks.append(f"[{name}]")
        if attachment_blocks:
            messages.append(
                {
                    "role": "system",
                    "content": "Attachments provided for this message:\n\n"
                    + "\n\n".join(attachment_blocks),
                }
            )
        messages.extend(history)

        try:
            config = self.resolve_model(session.get("model_id") or "")
            client = self._client_factory(config)
        except LLMError as exc:
            yield {"type": "error", "message": str(exc)}
            return

        collected: list[str] = []
        try:
            for delta in client.stream_chat(messages):
                collected.append(delta)
                yield {"type": "delta", "text": delta}
        except LLMError as exc:
            if collected:
                self.store.add_message(session_id, "assistant", "".join(collected))
            yield {"type": "error", "message": str(exc)}
            return
        answer = "".join(collected)
        if answer:
            self.store.add_message(session_id, "assistant", answer)
        current = self.store.get_session(session_id)
        yield {
            "type": "done",
            "session_id": session_id,
            "title": current.get("title") or "",
        }


__all__ = ["ChatService", "ClientFactory"]
