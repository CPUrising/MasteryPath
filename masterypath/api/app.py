"""REST + WS API (spec 05). Thin transport over LearningService / AgentLoop."""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
from typing import Any, Callable

from fastapi import Body, FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

from masterypath.agents.model_resolution import build_client, resolve_llm_config
from masterypath.agents.task_model import TaskModel
from masterypath.agents.turn_runner import TurnEvent, TurnRequest, TurnRunner
from masterypath.api.chat_routes import register_chat_routes
from masterypath.api.knowledge_routes import register_knowledge_routes
from masterypath.capabilities.mastery import mode as mode_policy
from masterypath.capabilities.mastery.tools import TOOLS, ToolContext
from masterypath.chat.service import ChatService, ClientFactory as ChatClientFactory
from masterypath.chat.store import ChatStore
from masterypath.knowledge.service import KnowledgeService
from masterypath.knowledge.store import KnowledgeStore
from masterypath.learning.outline import OutlineError
from masterypath.learning.models import TopicSource
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore, PreconditionError
from masterypath.knowledge.loader import scan_folder
from masterypath.settings import providers as provider_probe
from masterypath.settings.store import SECTIONS, SettingsStore, UnknownSection


def _cors_origins() -> list[str]:
    """Origins the browser UI may call from.

    A separate Next dev server (localhost:3000) talking to the API on :8001 is
    cross-origin, so without this every fetch fails with "Failed to fetch".
    Override with ``MASTERYPATH_CORS_ORIGINS`` (comma-separated); default allows
    any origin (no credentials are used).
    """
    raw = os.environ.get("MASTERYPATH_CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return ["*"]


def create_app(
    store: LearningStore,
    *,
    client_factory: Callable[[], Any] | None = None,
    source_map: dict[str, str] | None = None,
    selected_source_ids: set[str] | None = None,
    settings_store: SettingsStore | None = None,
    knowledge_store: KnowledgeStore | None = None,
    chat_store: ChatStore | None = None,
    chat_client_factory: ChatClientFactory | None = None,
    embedder_factory: Callable[[dict[str, Any]], Any] | None = None,
) -> FastAPI:
    app = FastAPI(title="MasteryPath")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    service = LearningService(
        store, source_map=source_map, selected_source_ids=selected_source_ids
    )
    settings = settings_store or SettingsStore(store.base_dir)
    knowledge_service = KnowledgeService(
        knowledge_store or KnowledgeStore(store.base_dir),
        settings,
        embedder_factory=embedder_factory,
    )
    chat_service = ChatService(
        chat_store or ChatStore(store.base_dir),
        settings,
        knowledge=knowledge_service,
        client_factory=chat_client_factory,
    )
    app.state.knowledge_service = knowledge_service
    app.state.chat_service = chat_service
    app.state.session_modes: dict[str, str] = {}

    def _build_llm_client(selection: Any = None, session_key: str = "") -> Any:
        """Resolve the model from settings (+ optional session selection)."""
        config = resolve_llm_config(settings, selection)
        config["session_key"] = session_key
        return build_client(config)

    if client_factory is not None:
        app.state.client_builder = lambda selection=None, session_key="": client_factory()
    else:
        app.state.client_builder = _build_llm_client
    task_model = TaskModel(client_factory=lambda: app.state.client_builder())
    turn_runner = TurnRunner(
        chat_service=chat_service,
        learning_service=service,
        store=store,
        client_builder=app.state.client_builder,
        session_modes=app.state.session_modes,
        knowledge_service=knowledge_service,
    )
    app.state.turn_runner = turn_runner

    def _session_mode(session_id: str) -> Any:
        session = store.get_session(session_id) if session_id else None
        if session is not None:
            return session.get("mode")
        return app.state.session_modes.get(session_id)

    def _ctx(path_id: str, session_id: str = "") -> ToolContext:
        return ToolContext(
            service=service,
            path_id=path_id,
            session_mode=_session_mode(session_id),
            session_id=session_id,
        )

    def _require_outline(session_id: str) -> None:
        current = _session_mode(session_id)
        # Unrecorded mode enforces nothing (INV-09).
        if current is not None and mode_policy.normalize_mode(current) != mode_policy.OUTLINE:
            raise HTTPException(status_code=409, detail="mode_conflict: outline mode required")

    # -- paths -------------------------------------------------------------
    @app.get("/learning/paths")
    def list_paths() -> list[dict[str, Any]]:
        out = []
        for progress in store.list_paths():
            out.append(
                {
                    "path_id": progress.path_id,
                    "name": progress.name,
                    "goal": progress.goal,
                    "objectives": sum(len(m.knowledge_points) for m in progress.modules),
                }
            )
        return out

    @app.post("/learning/paths", status_code=201)
    def create_path(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        path_id = str(payload.get("path_id") or "")
        if not path_id:
            raise HTTPException(status_code=422, detail="path_id required")
        try:
            service.create_path(
                path_id, goal=str(payload.get("goal") or ""), name=str(payload.get("name") or "")
            )
        except PreconditionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        kb_ids = payload.get("knowledge_base_ids")
        if isinstance(kb_ids, list) and kb_ids:
            sources = []
            for position, kb_id in enumerate(kb_ids):
                try:
                    kb = knowledge_service.get(str(kb_id))
                except Exception:
                    raise HTTPException(
                        status_code=404, detail=f"unknown knowledge base: {kb_id}"
                    )
                sources.append(
                    TopicSource(
                        id=f"kb:{kb['id']}",
                        kind="knowledge_base",
                        source_id=kb["id"],
                        label=kb["name"],
                        excerpt=str(kb.get("description") or ""),
                        position=position,
                        available=kb.get("status") == "ready",
                    )
                )
            service.set_knowledge_base_sources(path_id, sources)
        return service.get_state(path_id)

    @app.get("/learning/paths/{path_id}")
    def get_path(path_id: str) -> dict[str, Any]:
        state = service.get_state(path_id)
        if state["status"] == "missing":
            raise HTTPException(status_code=404, detail="unknown path")
        return state

    @app.delete("/learning/paths/{path_id}", status_code=204)
    def delete_path(path_id: str) -> None:
        service.delete(path_id)
        return None

    @app.patch("/learning/paths/{path_id}")
    def patch_path(path_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        if "name" in payload:
            try:
                return service.rename(path_id, str(payload.get("name") or ""))
            except PreconditionError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
        return service.get_state(path_id)

    @app.post("/learning/paths/{path_id}/redo")
    def redo(path_id: str) -> dict:
        try:
            return service.reset(path_id)
        except PreconditionError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.put("/learning/paths/{path_id}/review-settings")
    def review_settings(path_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        try:
            return service.set_review_settings(
                path_id, float(payload.get("desired_retention") or 0.9)
            )
        except PreconditionError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    # -- map (outline only) ------------------------------------------------
    @app.put("/learning/paths/{path_id}/map")
    def put_map(
        path_id: str,
        session_id: str = Query(...),
        payload: dict[str, Any] = Body(...),
    ) -> dict[str, Any]:
        _require_outline(session_id)
        try:
            if "ops" in payload:
                result = service.revise(path_id, payload["ops"])
                return {"status": result.status, "applied": result.applied}
            result = service.build(
                path_id, {"modules": payload.get("modules")}, confirm=bool(payload.get("confirm"))
            )
        except OutlineError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        if result.status == "refused_rebuild":
            raise HTTPException(status_code=409, detail="rebuild_requires_confirm")
        return {"status": result.status, "version": service.get_state(path_id)["version"]}

    @app.post("/learning/paths/{path_id}/rebuild")
    def rebuild(
        path_id: str,
        session_id: str = Query(...),
        payload: dict[str, Any] = Body(default={}),
    ) -> dict[str, Any]:
        _require_outline(session_id)
        if not payload.get("confirm"):
            raise HTTPException(status_code=409, detail="rebuild_requires_confirm")
        result = service.build(
            path_id, {"modules": payload.get("modules")}, confirm=True
        )
        return {"status": result.status, "rebuilt": result.rebuilt}

    @app.post("/learning/paths/{path_id}/objectives/{kp_id}/override")
    def override(path_id: str, kp_id: str, payload: dict[str, Any] = Body(default={})) -> dict:
        try:
            return service.override_mastery(path_id, kp_id, note=str(payload.get("note") or ""))
        except PreconditionError as exc:
            raise HTTPException(status_code=412, detail=str(exc))

    @app.post("/learning/paths/{path_id}/gaps/{gap_id}/resolve")
    def resolve(path_id: str, gap_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        try:
            gap = service.resolve_gap(path_id, gap_id, str(payload.get("action") or ""))
        except (OutlineError, PreconditionError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"gap_id": gap.id, "resolution": gap.resolution}

    # -- progress / events -------------------------------------------------
    @app.get("/learning/paths/{path_id}/mastery")
    def mastery(path_id: str) -> dict:
        state = service.get_state(path_id)
        if state["status"] == "missing":
            raise HTTPException(status_code=404, detail="unknown path")
        return state["map"]

    # -- knowledge base (folder sources) ----------------------------------
    @app.post("/learning/paths/{path_id}/sources")
    def attach_sources(path_id: str, payload: dict[str, Any] = Body(...)) -> list[dict]:
        folder = str(payload.get("folder") or "")
        if not folder:
            raise HTTPException(status_code=422, detail="folder required")
        try:
            sources = scan_folder(folder)
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return service.attach_sources(path_id, sources)

    @app.get("/learning/paths/{path_id}/sources")
    def list_sources(path_id: str) -> list[dict]:
        state = service.get_state(path_id)
        if state["status"] == "missing":
            raise HTTPException(status_code=404, detail="unknown path")
        return state["sources"]

    @app.put("/learning/paths/{path_id}/knowledge-bases")
    def set_path_knowledge_bases(
        path_id: str, payload: dict[str, Any] = Body(...)
    ) -> dict:
        """Set the path's default knowledge bases as ``knowledge_base`` sources."""
        kb_ids = payload.get("kb_ids")
        if not isinstance(kb_ids, list):
            raise HTTPException(status_code=422, detail="kb_ids must be an array")
        sources = []
        for position, kb_id in enumerate(kb_ids):
            try:
                kb = knowledge_service.get(str(kb_id))
            except Exception:
                raise HTTPException(status_code=404, detail=f"unknown knowledge base: {kb_id}")
            sources.append(
                TopicSource(
                    id=f"kb:{kb['id']}",
                    kind="knowledge_base",
                    source_id=kb["id"],
                    label=kb["name"],
                    excerpt=str(kb.get("description") or ""),
                    position=position,
                    available=kb.get("status") == "ready",
                )
            )
        service.set_knowledge_base_sources(path_id, sources)
        state = service.get_state(path_id)
        return {"knowledge_bases": state.get("knowledge_bases", []), "sources": state["sources"]}

    @app.get("/learning/paths/{path_id}/review-queue")
    def review_queue(path_id: str) -> list:
        return service.get_state(path_id)["due_reviews"]

    @app.get("/learning/paths/{path_id}/events")
    def events(path_id: str, since: int = 0) -> list[dict]:
        return store.events_since(path_id, since)

    @app.get("/learning/paths/{path_id}/suggest-question")
    def suggest_question(path_id: str) -> dict:
        state = service.get_state(path_id)
        if state["status"] == "missing":
            raise HTTPException(status_code=404, detail="unknown path")
        return {"suggestion": task_model.suggest_question(state)}

    # -- question bank (M6) ------------------------------------------------
    @app.get("/learning/paths/{path_id}/questions")
    def questions(path_id: str, tag: str | None = None) -> list[dict]:
        return service.list_questions(path_id, tag=tag)

    @app.post("/learning/questions/{entry_id}/tags")
    def tag_question(entry_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        try:
            return service.tag_question(entry_id, payload.get("tags") or [])
        except PreconditionError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    # -- capture / coverage / eval (ADR-017/018) --------------------------
    @app.get("/learning/paths/{path_id}/proposals")
    def proposals(path_id: str) -> list[dict]:
        state = service.get_state(path_id)
        if state["status"] == "missing":
            raise HTTPException(status_code=404, detail="unknown path")
        return state["proposals"]

    @app.post("/learning/paths/{path_id}/proposals/{proposal_id}/resolve")
    def resolve_proposal(path_id: str, proposal_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        try:
            return service.resolve_proposal(path_id, proposal_id, str(payload.get("action") or ""))
        except (OutlineError, PreconditionError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get("/learning/paths/{path_id}/coverage")
    def coverage(path_id: str) -> dict:
        report = service.get_coverage(path_id)
        if report is None:
            raise HTTPException(status_code=404, detail="unknown path")
        return report

    @app.post("/learning/paths/{path_id}/eval")
    def eval_outline(path_id: str) -> dict:
        result = service.eval_outline(path_id)
        if result is None:
            raise HTTPException(status_code=404, detail="unknown path")
        return result

    # -- settings (API configuration) -------------------------------------
    @app.get("/settings")
    def get_settings() -> dict:
        return settings.read()

    @app.get("/settings/{section}")
    def get_settings_section(section: str) -> Any:
        try:
            return settings.section(section)
        except UnknownSection:
            raise HTTPException(status_code=404, detail=f"unknown settings section: {section}")

    @app.put("/settings/{section}")
    def put_settings_section(section: str, payload: Any = Body(...)) -> Any:
        try:
            return settings.write_section(section, payload)
        except UnknownSection:
            raise HTTPException(status_code=404, detail=f"unknown settings section: {section}")

    # -- provider detection (read-only probes; never write configuration) --
    def _probe_fields(payload: dict[str, Any]) -> dict[str, Any]:
        """Merge posted fields over the saved provider named by ``provider_id``.

        The editor posts what is on screen; a masked/absent key and omitted
        fields fall back to the saved entry so "Test connection" works without
        re-typing a stored credential.
        """
        provider_id = str(payload.get("provider_id") or "")
        saved = next(
            (
                item
                for item in settings.section("providers")
                if isinstance(item, dict) and item.get("id") == provider_id
            ),
            {},
        )
        api_key = payload.get("api_key")
        if not api_key and provider_id:
            api_key = saved.get("api_key")
        return {
            "protocol": str(payload.get("protocol") or saved.get("protocol") or "openai"),
            "base_url": str(payload.get("base_url") or saved.get("base_url") or ""),
            "api_key": api_key,
            "service": str(payload.get("service") or ""),
        }

    @app.get("/settings/providers/catalog")
    def get_provider_catalog() -> list[dict[str, Any]]:
        return provider_probe.provider_catalog()

    @app.post("/settings/providers/probe")
    def probe_settings_provider(payload: dict[str, Any] = Body(default={})) -> dict:
        fields = _probe_fields(payload)
        return provider_probe.probe_provider(
            fields["protocol"],
            fields["base_url"],
            fields["api_key"],
            service=fields["service"],
        )

    @app.post("/settings/providers/fetch-models")
    def fetch_settings_provider_models(payload: dict[str, Any] = Body(default={})) -> dict:
        fields = _probe_fields(payload)
        return provider_probe.fetch_models(
            fields["protocol"],
            fields["base_url"],
            fields["api_key"],
            service=fields["service"],
        )

    @app.post("/settings/models/detect-dimension")
    def detect_settings_model_dimension(payload: dict[str, Any] = Body(default={})) -> dict:
        fields = _probe_fields(payload)
        return provider_probe.detect_dimension(
            fields["protocol"],
            fields["base_url"],
            fields["api_key"],
            str(payload.get("model") or ""),
        )

    # -- sessions / mode ---------------------------------------------------
    @app.get("/learning/paths/{path_id}/sessions")
    def list_sessions(path_id: str) -> dict:
        return {"path_id": path_id, "sessions": service.list_sessions(path_id)}

    @app.get("/learning/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        session = service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session")
        return session

    @app.put("/learning/paths/{path_id}/sessions/{session_id}/mode")
    def set_mode(path_id: str, session_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        requested = str(payload.get("mode") or "").strip().lower()
        if requested not in mode_policy.MODES:
            raise HTTPException(
                status_code=422,
                detail="mode must be one of: " + ", ".join(mode_policy.MODES),
            )
        state = service.get_state(path_id)
        if state["status"] == "missing":
            raise HTTPException(status_code=404, detail="unknown path")
        has_outline = bool(state["map"])
        refusal = mode_policy.admission_error(requested, has_outline=has_outline)
        if refusal:
            raise HTTPException(status_code=409, detail=refusal)
        app.state.session_modes[session_id] = requested
        service.set_session_mode(path_id, session_id, requested)
        return {"session_id": session_id, "mode": requested, "actor": payload.get("actor", "learner")}

    @app.patch("/learning/paths/{path_id}/sessions/{session_id}")
    def patch_session(
        path_id: str, session_id: str, payload: dict[str, Any] = Body(...)
    ) -> dict:
        """Persist per-session preferences (model selection, knowledge bases)."""
        preferences = payload.get("preferences")
        if not isinstance(preferences, dict):
            preferences = {
                key: payload[key]
                for key in ("llm_selection", "knowledge_bases")
                if key in payload
            }
        if store.get_session(session_id) is None:
            store.upsert_session(
                {
                    "session_id": session_id,
                    "path_id": path_id,
                    "mode": mode_policy.normalize_mode(payload.get("mode")),
                }
            )
        updated = store.set_session_preferences(session_id, preferences)
        if updated is None:
            raise HTTPException(status_code=404, detail="unknown session")
        return updated

    # -- study via REST (no WS / no LLM needed) ---------------------------
    def _run_tool(tool_name: str, path_id: str, payload: dict[str, Any]) -> dict:
        session_id = str(payload.get("session_id") or "")
        result = TOOLS[tool_name].execute(payload, _ctx(path_id, session_id))
        if not result.ok:
            raise HTTPException(status_code=422, detail=result.content)
        return {"ok": True, "content": result.content, **result.metadata}

    @app.post("/learning/paths/{path_id}/quiz")
    def quiz(path_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        return _run_tool("mastery_quiz", path_id, payload)

    @app.post("/learning/paths/{path_id}/grade")
    def grade(path_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        return _run_tool("mastery_grade", path_id, payload)

    @app.post("/learning/paths/{path_id}/assess")
    def assess(path_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        return _run_tool("mastery_assess", path_id, payload)

    @app.post("/learning/paths/{path_id}/skip-question")
    def skip_question(path_id: str, payload: dict[str, Any] = Body(default={})) -> dict:
        return _run_tool("mastery_skip_question", path_id, payload)

    # -- WS turn -----------------------------------------------------------
    @app.websocket("/ws")
    async def ws_turn(websocket: WebSocket) -> None:
        await websocket.accept()
        payload = await websocket.receive_json()
        request = TurnRequest(
            capability="mastery_path",
            session_id=str(payload.get("session_id") or ""),
            path_id=str(payload.get("path_id") or ""),
            mode=str(payload.get("mode") or ""),
            turn_id=str(payload.get("turn_id") or ""),
            llm_selection=payload.get("llm_selection"),
            message=str(payload.get("message") or ""),
        )
        # The turn runs synchronously (blocking provider I/O). Run it off the
        # event loop and bridge events through a queue: blocking the loop would
        # starve the WebSocket keepalive and the server would drop the socket
        # mid-generation ("websocket error" in the browser).
        mailbox: queue.Queue[Any] = queue.Queue()
        done = object()

        def worker() -> None:
            try:
                for event in app.state.turn_runner.run(request):
                    mailbox.put(event)
            except Exception as exc:  # noqa: BLE001 - report, never crash the socket
                logger.exception("ws turn failed")
                mailbox.put(
                    TurnEvent(
                        "error",
                        {
                            "error_code": "internal_error",
                            "message": f"The turn failed: {exc}",
                            "retryable": False,
                        },
                    )
                )
            finally:
                mailbox.put(done)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            event = await asyncio.to_thread(mailbox.get)
            if event is done:
                break
            await websocket.send_json({"type": event.type, "data": event.data})
        await websocket.close()

    # -- knowledge bases / general chat -----------------------------------
    register_knowledge_routes(app, knowledge_service)
    register_chat_routes(app, turn_runner)

    # -- question bank (global view, aggregated across paths) -------------
    @app.get("/questions")
    def all_questions(path_id: str | None = None, tag: str | None = None) -> list[dict]:
        if path_id:
            return service.list_questions(path_id, tag=tag)
        out: list[dict] = []
        for progress in store.list_paths():
            name = progress.name or progress.path_id
            for entry in store.list_bank_entries(progress.path_id):
                if tag and tag not in entry.tags:
                    continue
                row = entry.model_dump()
                row["path_name"] = name
                out.append(row)
        return out

    return app


__all__ = ["create_app"]
