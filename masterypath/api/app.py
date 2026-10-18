"""REST + WS API (spec 05). Thin transport over LearningService / AgentLoop."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Body, FastAPI, HTTPException, Query, WebSocket

from masterypath.agents.llm import DeepSeekClient
from masterypath.agents.loop import AgentLoop
from masterypath.agents.task_model import TaskModel
from masterypath.capabilities.mastery import mode as mode_policy
from masterypath.capabilities.mastery.tools import TOOLS, ToolContext
from masterypath.learning.outline import OutlineError
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore, PreconditionError
from masterypath.knowledge.loader import scan_folder
from masterypath.settings.store import SECTIONS, SettingsStore, UnknownSection


def create_app(
    store: LearningStore,
    *,
    client_factory: Callable[[], Any] | None = None,
    source_map: dict[str, str] | None = None,
    selected_source_ids: set[str] | None = None,
    settings_store: SettingsStore | None = None,
) -> FastAPI:
    app = FastAPI(title="MasteryPath")
    service = LearningService(
        store, source_map=source_map, selected_source_ids=selected_source_ids
    )
    settings = settings_store or SettingsStore(store.base_dir)
    app.state.session_modes: dict[str, str] = {}
    app.state.client_factory = client_factory or (lambda: DeepSeekClient())
    task_model = TaskModel(client_factory=app.state.client_factory)

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
        requested = mode_policy.normalize_mode(payload.get("mode"))
        state = service.get_state(path_id)
        has_outline = state["status"] == "active" and bool(state["map"])
        refusal = mode_policy.admission_error(requested, has_outline=has_outline)
        if refusal:
            raise HTTPException(status_code=409, detail=refusal)
        app.state.session_modes[session_id] = requested
        service.set_session_mode(path_id, session_id, requested)
        return {"session_id": session_id, "mode": requested, "actor": payload.get("actor", "learner")}

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
        request = await websocket.receive_json()
        session_id = str(request.get("session_id") or "")
        path_id = str(request.get("path_id") or "")
        turn_id = str(request.get("turn_id") or "")
        session_mode = _session_mode(session_id)
        if session_mode is None:
            session_mode = request.get("mode")
        ctx = ToolContext(
            service=service,
            path_id=path_id,
            session_mode=session_mode,
            session_id=session_id,
            turn_id=turn_id,
        )
        loop = AgentLoop(TOOLS)
        message = str(request.get("message") or "")
        events_out = loop.run(
            app.state.client_factory(),
            [{"role": "user", "content": message}],
            ctx,
        )
        for event in events_out:
            await websocket.send_json({"type": event.type, "data": event.data})

        # Persist the turn (best-effort; a persistence failure must not break
        # the stream the learner already saw).
        text = "".join(
            str(event.data.get("text", ""))
            for event in events_out
            if event.type == "text_delta"
        )
        card = None
        for event in events_out:
            if event.type == "tool_result":
                metadata = event.data.get("metadata") or {}
                if metadata.get("question_card"):
                    card = metadata["question_card"]
        try:
            if session_id:
                service.record_turn(
                    path_id,
                    session_id,
                    user_text=message,
                    assistant_text=text,
                    mode=mode_policy.normalize_mode(session_mode),
                    turn_id=turn_id,
                    card=card,
                )
        except Exception:  # pragma: no cover - persistence is best-effort
            pass
        await websocket.close()

    return app


__all__ = ["create_app"]
