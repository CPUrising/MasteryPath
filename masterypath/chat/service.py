"""General chat turns: model resolution, knowledge context, streaming."""

from __future__ import annotations

from typing import Any, Callable, Iterator

from masterypath.agents.llm import LLMError, OpenAICompatibleClient
from masterypath.agents.model_resolution import build_client, resolve_llm_config
from masterypath.chat.store import ChatStore, UnknownSession
from masterypath.knowledge.context import knowledge_context
from masterypath.settings.store import SettingsStore

ClientFactory = Callable[[dict[str, Any]], Any]

_SYSTEM = (
    "You are MasteryPath, a study assistant. Answer the learner directly and "
    "concisely in their language. When reference material is provided below, "
    "ground your answer in it and cite the source file name."
)


def _default_client_factory(config: dict[str, Any]) -> OpenAICompatibleClient:
    return build_client(config)


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
        selection = None
        if model_id:
            selection = {"model_id": model_id}
        return resolve_llm_config(self.settings, selection)

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
        return knowledge_context(self.knowledge, kb_ids, query)

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
            preferences = session.get("preferences") or {}
            selection = preferences.get("llm_selection")
            if not selection and session.get("model_id"):
                selection = {"model_id": session["model_id"]}
            config = resolve_llm_config(self.settings, selection)
            config["session_key"] = session_id
            client = self._client_factory(config)
        except LLMError as exc:
            yield {"type": "error", "message": str(exc), "error_code": exc.code, "retryable": exc.retryable}
            return

        collected: list[str] = []
        try:
            for delta in client.stream_chat(messages):
                collected.append(delta)
                yield {"type": "text_delta", "text": delta}
        except LLMError as exc:
            if collected:
                self.store.add_message(session_id, "assistant", "".join(collected))
            yield {"type": "error", "message": str(exc), "error_code": exc.code, "retryable": exc.retryable}
            return
        answer = "".join(collected)
        if answer:
            self.store.add_message(session_id, "assistant", answer)
        current = self.store.get_session(session_id)
        yield {
            "type": "turn_end",
            "reason": "done",
            "session_id": session_id,
            "title": current.get("title") or "",
        }


__all__ = ["ChatService", "ClientFactory"]
