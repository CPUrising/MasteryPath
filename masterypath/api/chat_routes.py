"""General chat REST + SSE routes."""

from __future__ import annotations

import json
from typing import Any, Iterator

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from masterypath.agents.turn_runner import TurnRequest, TurnRunner
from masterypath.chat.service import ChatService
from masterypath.chat.store import UnknownSession


def _sse(events: Iterator[Any]) -> Iterator[str]:
    for event in events:
        payload = {"type": event.type, "data": event.data}
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def register_chat_routes(app: FastAPI, runner: TurnRunner) -> None:
    service: ChatService = runner.chat_service
    @app.get("/chat/sessions")
    def list_chat_sessions() -> list[dict[str, Any]]:
        return service.list_sessions()

    @app.post("/chat/sessions", status_code=201)
    def create_chat_session(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        return service.create_session(
            title=str(payload.get("title") or ""),
            model_id=str(payload.get("model_id") or ""),
            kb_ids=payload.get("kb_ids") if isinstance(payload.get("kb_ids"), list) else [],
        )

    @app.get("/chat/sessions/{session_id}")
    def get_chat_session(session_id: str) -> dict[str, Any]:
        try:
            return service.session_detail(session_id)
        except UnknownSession as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.patch("/chat/sessions/{session_id}")
    def update_chat_session(
        session_id: str, payload: dict[str, Any] = Body(...)
    ) -> dict[str, Any]:
        try:
            return service.update_session(session_id, payload)
        except UnknownSession as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.delete("/chat/sessions/{session_id}", status_code=204)
    def delete_chat_session(session_id: str) -> None:
        try:
            service.delete_session(session_id)
        except UnknownSession as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/chat/sessions/{session_id}/turns")
    def chat_turn(session_id: str, payload: dict[str, Any] = Body(...)) -> StreamingResponse:
        attachments = payload.get("attachments")
        if not isinstance(attachments, list):
            attachments = []
        events = runner.run(
            TurnRequest(
                capability="chat",
                session_id=session_id,
                message=str(payload.get("message") or ""),
                attachments=attachments,
            )
        )
        return StreamingResponse(
            _sse(events),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )


__all__ = ["register_chat_routes"]
