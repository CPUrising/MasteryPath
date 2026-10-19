"""Knowledge-base REST routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile

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
        index_config = payload.get("index_config")
        if not isinstance(index_config, dict) and (
            payload.get("chunk_size") is not None or payload.get("chunk_overlap") is not None
        ):
            index_config = {
                "chunk_size": payload.get("chunk_size"),
                "chunk_overlap": payload.get("chunk_overlap"),
            }
        try:
            return service.create(
                str(payload.get("name") or ""),
                mode=str(payload.get("mode") or "import"),
                embedding_model_id=payload.get("embedding_model_id"),
                description=str(payload.get("description") or ""),
                index_config=index_config if isinstance(index_config, dict) else None,
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
        fields = dict(payload)
        if "index_config" not in fields and (
            fields.get("chunk_size") is not None or fields.get("chunk_overlap") is not None
        ):
            fields["index_config"] = {
                "chunk_size": fields.pop("chunk_size", None),
                "chunk_overlap": fields.pop("chunk_overlap", None),
            }
        try:
            return service.update(kb_id, fields)
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

    @app.get("/knowledge-bases/{kb_id}/progress")
    def knowledge_base_progress(kb_id: str) -> dict[str, Any]:
        try:
            return service.progress(kb_id)
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)

    @app.post("/knowledge-bases/{kb_id}/upload")
    async def upload_knowledge_files(
        kb_id: str,
        files: list[UploadFile] = File(...),
        paths: str = Form(""),
        conflict: str = Form("overwrite"),
    ) -> dict[str, Any]:
        try:
            relative = json.loads(paths) if paths else []
        except ValueError:
            relative = []
        if not isinstance(relative, list):
            relative = []
        uploads: list[tuple[str, bytes]] = []
        for index, upload in enumerate(files):
            rel = (
                str(relative[index])
                if index < len(relative) and relative[index]
                else (upload.filename or f"upload-{index}.txt")
            )
            uploads.append((rel, await upload.read()))
        try:
            return service.upload(kb_id, uploads, conflict=conflict or "overwrite")
        except UnknownKnowledgeBase as exc:
            raise _missing(exc)
        except KnowledgeError as exc:
            raise HTTPException(status_code=422, detail=str(exc))


__all__ = ["register_knowledge_routes"]
