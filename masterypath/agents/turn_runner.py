"""One turn chain for every capability.

``ChatService`` (general chat) and the mastery tutor used to be separate paths
with their own transports. Both now build the same :class:`TurnRequest` and read
the same :class:`TurnEvent` stream, so the transports are thin adapters and the
event vocabulary is identical:

``text_delta`` · ``tool_call`` · ``tool_result`` · ``question_card`` ·
``turn_end`` · ``error``

Generation is still non-streaming for mastery (the loop returns its events at
once); incremental streaming is a later step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Callable, Iterator

from masterypath.agents.llm import LLMError
from masterypath.agents.loop import AgentLoop
from masterypath.capabilities.mastery import mode as mode_policy
from masterypath.capabilities.mastery.tools import TOOLS, ToolContext
from masterypath.chat.service import ChatService
from masterypath.knowledge.context import knowledge_context
from masterypath.learning.question_card import QUESTION_CARD_KEY
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore

ClientBuilder = Callable[..., Any]

logger = logging.getLogger(__name__)


@dataclass
class TurnRequest:
    capability: str = "chat"  # "chat" | "mastery_path"
    session_id: str = ""
    message: str = ""
    path_id: str = ""
    mode: str = ""
    turn_id: str = ""
    llm_selection: dict[str, Any] | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TurnEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


class TurnRunner:
    def __init__(
        self,
        *,
        chat_service: ChatService,
        learning_service: LearningService,
        store: LearningStore,
        client_builder: ClientBuilder,
        session_modes: dict[str, str],
        knowledge_service: Any | None = None,
    ) -> None:
        self.chat_service = chat_service
        self.learning_service = learning_service
        self.store = store
        self.client_builder = client_builder
        self.session_modes = session_modes
        self.knowledge_service = knowledge_service

    # -- public ------------------------------------------------------------
    def run(self, request: TurnRequest) -> Iterator[TurnEvent]:
        if request.capability == "mastery_path":
            yield from self._run_mastery(request)
            return
        for event in self.chat_service.stream_turn(
            request.session_id, request.message, attachments=request.attachments
        ):
            kind = str(event.get("type") or "text_delta")
            yield TurnEvent(kind, {k: v for k, v in event.items() if k != "type"})

    # -- mastery -----------------------------------------------------------
    def _session_mode(self, session_id: str, fallback: str = "") -> Any:
        session = self.store.get_session(session_id) if session_id else None
        if session is not None:
            return session.get("mode")
        return mode_policy.enforced_mode(
            self.session_modes.get(session_id) or fallback or None
        )

    def _knowledge_base_ids(self, request: TurnRequest) -> list[str]:
        """Session override (three-state) else the path's knowledge_base sources."""
        session = self.store.get_session(request.session_id) if request.session_id else None
        preferences = (session or {}).get("preferences") or {}
        if "knowledge_bases" in preferences and preferences.get("knowledge_bases") is not None:
            values = preferences.get("knowledge_bases")
            return [str(item) for item in values] if isinstance(values, list) else []
        progress = self.store.load(request.path_id) if request.path_id else None
        if progress is None:
            return []
        return [
            source.source_id or source.id
            for source in progress.sources
            if source.kind == "knowledge_base"
        ]

    def _run_mastery(self, request: TurnRequest) -> Iterator[TurnEvent]:
        session = self.store.get_session(request.session_id) if request.session_id else None
        selection = request.llm_selection
        if not selection and session is not None:
            selection = (session.get("preferences") or {}).get("llm_selection")
        ctx = ToolContext(
            service=self.learning_service,
            path_id=request.path_id,
            session_mode=self._session_mode(request.session_id, request.mode),
            session_id=request.session_id,
            turn_id=request.turn_id,
        )

        def bind_mode(value: str) -> None:
            ctx.session_mode = value
            ctx.mode_changed = True

        ctx.bind_mode = bind_mode
        context = knowledge_context(
            self.knowledge_service,
            self._knowledge_base_ids(request),
            request.message,
        )
        if request.path_id:
            try:
                snapshot = TOOLS["mastery_status"].execute({}, ctx)
            except Exception:  # noqa: BLE001 - state must never sink the turn
                logger.warning("mastery_status snapshot failed", exc_info=True)
            else:
                if snapshot.ok:
                    header = (
                        "[Current-turn mastery_status snapshot]\n"
                        "The runtime already read mastery_status for this turn. "
                        "Use it directly; refresh with mastery_status after "
                        "changing the path, mode, outline or progress.\n"
                    )
                    context = f"{header}{snapshot.content}" + (
                        f"\n\n{context}" if context else ""
                    )
        loop = AgentLoop(TOOLS)
        try:
            client = self.client_builder(selection, request.session_id)
            events = loop.run(
                client,
                [{"role": "user", "content": request.message}],
                ctx,
                extra_context=context,
            )
        except LLMError as exc:
            yield TurnEvent(
                "error",
                {
                    "error_code": exc.code,
                    "message": str(exc),
                    "retryable": exc.retryable,
                },
            )
            return
        except Exception as exc:  # noqa: BLE001 - never close the socket silently
            logger.exception("mastery turn failed")
            yield TurnEvent(
                "error",
                {
                    "error_code": "internal_error",
                    "message": f"The turn failed: {exc}",
                    "retryable": False,
                },
            )
            return

        for event in events:
            yield TurnEvent(event.type, dict(event.data))
            if event.type == "tool_result":
                card = (event.data.get("metadata") or {}).get(QUESTION_CARD_KEY)
                if card:
                    yield TurnEvent("question_card", dict(card))

        final_mode = mode_policy.normalize_mode(ctx.session_mode)
        if ctx.mode_changed:
            yield TurnEvent("session_meta", {"mastery_session_mode": final_mode})
        self._persist_mastery_turn(request, events, final_mode=final_mode)

    def _persist_mastery_turn(
        self,
        request: TurnRequest,
        events: list[Any],
        *,
        final_mode: str | None = None,
    ) -> None:
        if not request.session_id:
            return
        text = "".join(
            str(event.data.get("text", ""))
            for event in events
            if event.type == "text_delta"
        )
        card = None
        for event in events:
            if event.type == "tool_result":
                metadata = event.data.get("metadata") or {}
                if metadata.get(QUESTION_CARD_KEY):
                    card = metadata[QUESTION_CARD_KEY]
        session_mode = final_mode or mode_policy.normalize_mode(
            self._session_mode(request.session_id, request.mode)
        )
        try:
            self.learning_service.record_turn(
                request.path_id,
                request.session_id,
                user_text=request.message,
                assistant_text=text,
                mode=session_mode,
                turn_id=request.turn_id,
                card=card,
            )
        except Exception:  # noqa: BLE001 - persistence is best-effort
            pass


__all__ = ["TurnEvent", "TurnRequest", "TurnRunner"]
