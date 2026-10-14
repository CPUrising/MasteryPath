"""REST + WS API (spec 05). Thin transport over LearningService / AgentLoop."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Body, FastAPI, HTTPException, Query, WebSocket

from masterypath.agents.llm import DeepSeekClient
from masterypath.agents.loop import AgentLoop
from masterypath.capabilities.mastery import mode as mode_policy
from masterypath.capabilities.mastery.tools import TOOLS, ToolContext
from masterypath.learning.outline import OutlineError
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore, PreconditionError


def create_app(
    store: LearningStore,
    *,
    client_factory: Callable[[], Any] | None = None,
    source_map: dict[str, str] | None = None,
    selected_source_ids: set[str] | None = None,
) -> FastAPI:
    app = FastAPI(title="MasteryPath")
    service = LearningService(
        store, source_map=source_map, selected_source_ids=selected_source_ids
    )
    app.state.session_modes: dict[str, str] = {}
    app.state.client_factory = client_factory or (lambda: DeepSeekClient())

    def _require_outline(session_id: str) -> None:
        current = app.state.session_modes.get(session_id)
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
        return None

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

    @app.get("/learning/paths/{path_id}/review-queue")
    def review_queue(path_id: str) -> list:
        return service.get_state(path_id)["due_reviews"]

    @app.get("/learning/paths/{path_id}/events")
    def events(path_id: str, since: int = 0) -> list[dict]:
        return store.events_since(path_id, since)

    # -- sessions / mode ---------------------------------------------------
    @app.put("/learning/paths/{path_id}/sessions/{session_id}/mode")
    def set_mode(path_id: str, session_id: str, payload: dict[str, Any] = Body(...)) -> dict:
        requested = mode_policy.normalize_mode(payload.get("mode"))
        state = service.get_state(path_id)
        has_outline = state["status"] == "active" and bool(state["map"])
        refusal = mode_policy.admission_error(requested, has_outline=has_outline)
        if refusal:
            raise HTTPException(status_code=409, detail=refusal)
        app.state.session_modes[session_id] = requested
        return {"session_id": session_id, "mode": requested, "actor": payload.get("actor", "learner")}

    # -- WS turn -----------------------------------------------------------
    @app.websocket("/ws")
    async def ws_turn(websocket: WebSocket) -> None:
        await websocket.accept()
        request = await websocket.receive_json()
        session_id = str(request.get("session_id") or "")
        path_id = str(request.get("path_id") or "")
        session_mode = app.state.session_modes.get(session_id, request.get("mode"))
        ctx = ToolContext(
            service=service,
            path_id=path_id,
            session_mode=session_mode,
            session_id=session_id,
            turn_id=str(request.get("turn_id") or ""),
        )
        loop = AgentLoop(TOOLS)
        events_out = loop.run(
            app.state.client_factory(),
            [{"role": "user", "content": str(request.get("message") or "")}],
            ctx,
        )
        for event in events_out:
            await websocket.send_json({"type": event.type, "data": event.data})
        await websocket.close()

    return app


__all__ = ["create_app"]
