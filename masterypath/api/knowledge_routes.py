"""Knowledge-base REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException

from masterypath.knowledge.service import KnowledgeError, KnowledgeService
from masterypath.knowledge.store import UnknownKnowledgeBase


def register_knowledge_routes(app: FastAPI, service: KnowledgeService) -> None:
    def _missing(exc: Exception) -> HTTPException:
        return HTTPException(status_code=404, detail=str(exc))

    @app.get("/knowledge-bases")
    def list_knowledge_bases() -> list[dict[str, Any]]:
        return service.list()

    @app.post("/knowledge-bases", status_code=201)
    def create_knowledge_base(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return service.create(
                str(payload.get("name") or ""),
                mode=str(payload.get("mode") or "import"),
                embedding_model_id=payload.get("embedding_model_id"),
                description=str(payload.get("description") or ""),
            )
        except KnowledgeError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get("/knowledge-bases/{kb_id}")
    def get_knowledge_base(kb_id: str) -> dict[str, Any]:
        try:
            return service.get(kb_id)
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)

    @app.patch("/knowledge-bases/{kb_id}")
    def update_knowledge_base(
        kb_id: str, payload: dict[str, Any] = Body(...)
    ) -> dict[str, Any]:
        try:
            return service.update(kb_id, payload)
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)
        except KnowledgeError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.delete("/knowledge-bases/{kb_id}", status_code=204)
    def delete_knowledge_base(kb_id: str) -> None:
        try:
            service.delete(kb_id)
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)

    @app.get("/knowledge-bases/{kb_id}/files")
    def list_knowledge_files(kb_id: str) -> list[dict[str, Any]]:
        try:
            return service.files(kb_id)
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)

    @app.delete("/knowledge-bases/{kb_id}/files/{rel_path:path}", status_code=204)
    def delete_knowledge_file(kb_id: str, rel_path: str) -> None:
        try:
            service.remove_file(kb_id, rel_path)
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)
        except KnowledgeError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/knowledge-bases/{kb_id}/folders")
    def add_knowledge_folder(
        kb_id: str, payload: dict[str, Any] = Body(...)
    ) -> dict[str, Any]:
        folder = str(payload.get("folder") or "")
        if not folder:
            raise HTTPException(status_code=422, detail="folder required")
        mode = str(payload.get("mode") or "import")
        try:
            if mode == "link":
                return service.add_linked_folder(kb_id, folder)
            return service.import_folder(kb_id, folder)
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)
        except KnowledgeError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.delete("/knowledge-bases/{kb_id}/linked-folders/{folder_id}", status_code=200)
    def remove_knowledge_folder(kb_id: str, folder_id: str) -> dict[str, Any]:
        try:
            return service.remove_linked_folder(kb_id, folder_id)
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)

    @app.post("/knowledge-bases/{kb_id}/reindex")
    def reindex_knowledge_base(kb_id: str) -> dict[str, Any]:
        try:
            return service.reindex(kb_id)
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)


__all__ = ["register_knowledge_routes"]
