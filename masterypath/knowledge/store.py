"""Knowledge-base storage: metadata, imported files, and linked folders.

Layout under ``<base_dir>/knowledge_bases``::

    <kb_id>/
      kb.json          metadata
      raw/             one-time imported files (structure preserved)
      index/           LlamaIndex persisted vector store

No secrets live here: the embedding provider is resolved from settings each
time an index is built or queried.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import time
from typing import Any

from masterypath.knowledge.loader import SUPPORTED_EXTENSIONS, _SKIP_DIRS, read_text

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_BAD_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


class KnowledgeError(RuntimeError):
    pass


class UnknownKnowledgeBase(KnowledgeError):
    pass


def _slug(name: str) -> str:
    cleaned = _BAD_NAME.sub("", (name or "").strip()).strip(" .")
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:48] or "kb"


def _now() -> float:
    return time.time()


def iso(timestamp: float | None) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat()


def _iter_source_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    files: list[Path] = []
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file():
            continue
        try:
            rel_parts = candidate.relative_to(root).parts
        except ValueError:
            continue
        if any(part.startswith(".") or part in _SKIP_DIRS for part in rel_parts):
            continue
        if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        files.append(candidate)
    return files


class KnowledgeStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir) / "knowledge_bases"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # -- paths -------------------------------------------------------------
    def _dir(self, kb_id: str) -> Path:
        if not _SAFE_ID.match(kb_id or ""):
            raise UnknownKnowledgeBase(kb_id)
        path = (self.base_dir / kb_id).resolve()
        if self.base_dir.resolve() not in path.parents:
            raise UnknownKnowledgeBase(kb_id)
        return path

    def _meta_path(self, kb_id: str) -> Path:
        return self._dir(kb_id) / "kb.json"

    def raw_dir(self, kb_id: str) -> Path:
        return self._dir(kb_id) / "raw"

    def index_dir(self, kb_id: str) -> Path:
        return self._dir(kb_id) / "index"

    # -- metadata ----------------------------------------------------------
    def _load(self, kb_id: str) -> dict[str, Any]:
        path = self._meta_path(kb_id)
        if not path.exists():
            raise UnknownKnowledgeBase(kb_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise KnowledgeError(f"knowledge base metadata is unreadable: {kb_id}") from exc
        if not isinstance(data, dict):
            raise KnowledgeError(f"knowledge base metadata is invalid: {kb_id}")
        return data

    def _save(self, kb_id: str, meta: dict[str, Any]) -> dict[str, Any]:
        meta["updated_at"] = _now()
        meta["disk_path"] = str(self._dir(kb_id))
        path = self._meta_path(kb_id)
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return meta

    def _present(self, meta: dict[str, Any]) -> dict[str, Any]:
        kb_id = str(meta.get("id") or "")
        try:
            raw = self.raw_dir(kb_id)
            meta["doc_count"] = len(_iter_source_files(raw))
        except (KnowledgeError, OSError):
            meta["doc_count"] = 0
        meta.setdefault("status", "empty")
        meta.setdefault("linked_folders", [])
        meta.setdefault("rag_provider", "llamaindex")
        meta.setdefault("search_mode", "vector")
        meta["created_at_iso"] = iso(meta.get("created_at"))
        meta["updated_at_iso"] = iso(meta.get("updated_at"))
        meta["last_indexed_at_iso"] = iso(meta.get("last_indexed_at"))
        return meta

    def list(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.base_dir.glob("*/kb.json"):
            try:
                meta = self._load(path.parent.name)
            except KnowledgeError:
                continue
            rows.append(self._present(meta))
        rows.sort(key=lambda item: item.get("updated_at") or 0, reverse=True)
        return rows

    def get(self, kb_id: str) -> dict[str, Any]:
        return self._present(self._load(kb_id))

    def create(
        self,
        name: str,
        *,
        mode: str = "import",
        embedding_model: dict[str, Any] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        display = (name or "").strip()
        if not display:
            raise KnowledgeError("A knowledge base name is required.")
        base_id = _slug(display)
        kb_id = base_id
        counter = 2
        while (self.base_dir / kb_id).exists():
            kb_id = f"{base_id}-{counter}"
            counter += 1
        directory = self.base_dir / kb_id
        (directory / "raw").mkdir(parents=True, exist_ok=True)
        (directory / "index").mkdir(parents=True, exist_ok=True)
        now = _now()
        meta: dict[str, Any] = {
            "id": kb_id,
            "name": display,
            "description": (description or "").strip(),
            "mode": "link" if mode == "link" else "import",
            "rag_provider": "llamaindex",
            "search_mode": "vector",
            "embedding_model": embedding_model or {},
            "status": "empty",
            "error": "",
            "created_at": now,
            "updated_at": now,
            "last_indexed_at": None,
            "linked_folders": [],
        }
        self._save(kb_id, meta)
        return self._present(meta)

    def update(self, kb_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        meta = self._load(kb_id)
        allowed = {"name", "description", "embedding_model", "status", "error"}
        for key, value in fields.items():
            if key in allowed:
                meta[key] = value
        if "name" in fields and not str(meta.get("name") or "").strip():
            raise KnowledgeError("A knowledge base name is required.")
        return self._present(self._save(kb_id, meta))

    def delete(self, kb_id: str) -> None:
        directory = self._dir(kb_id)
        if not directory.exists():
            raise UnknownKnowledgeBase(kb_id)
        shutil.rmtree(directory)

    def set_index_result(
        self,
        kb_id: str,
        *,
        status: str,
        error: str = "",
        last_indexed_at: float | None = None,
        embedding_model: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = self._load(kb_id)
        meta["status"] = status
        meta["error"] = error
        if last_indexed_at:
            meta["last_indexed_at"] = last_indexed_at
        if embedding_model is not None:
            meta["embedding_model"] = embedding_model
        return self._present(self._save(kb_id, meta))

    # -- files & folders ---------------------------------------------------
    def files(self, kb_id: str) -> list[dict[str, Any]]:
        root = self.raw_dir(kb_id)
        rows = []
        for path in _iter_source_files(root):
            stat = path.stat()
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": stat.st_size,
                    "modified_at": iso(stat.st_mtime),
                }
            )
        return rows

    def remove_file(self, kb_id: str, rel_path: str) -> None:
        root = self.raw_dir(kb_id).resolve()
        target = (root / rel_path).resolve()
        if root not in target.parents:
            raise KnowledgeError("Invalid file path.")
        if not target.is_file():
            raise KnowledgeError("File not found.")
        target.unlink()

    def import_folder(self, kb_id: str, folder: str) -> int:
        source = Path(folder).expanduser()
        if not source.exists() or not source.is_dir():
            raise KnowledgeError(f"Folder not found: {folder}")
        root = self.raw_dir(kb_id)
        copied = 0
        for path in _iter_source_files(source):
            rel = path.relative_to(source)
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied += 1
        self._save(kb_id, self._load(kb_id))
        return copied

    def add_linked_folder(self, kb_id: str, folder: str) -> dict[str, Any]:
        source = Path(folder).expanduser()
        if not source.exists() or not source.is_dir():
            raise KnowledgeError(f"Folder not found: {folder}")
        meta = self._load(kb_id)
        rows = meta.setdefault("linked_folders", [])
        resolved = str(source.resolve())
        if any(item.get("path") == resolved for item in rows):
            raise KnowledgeError("That folder is already linked.")
        entry = {
            "id": f"folder-{int(_now() * 1000)}",
            "path": resolved,
            "file_count": len(_iter_source_files(source)),
            "added_at": _now(),
            "added_at_iso": iso(_now()),
            "last_sync": None,
        }
        rows.append(entry)
        self._save(kb_id, meta)
        return entry

    def remove_linked_folder(self, kb_id: str, folder_id: str) -> None:
        meta = self._load(kb_id)
        rows = [
            item
            for item in meta.get("linked_folders", [])
            if item.get("id") != folder_id
        ]
        meta["linked_folders"] = rows
        self._save(kb_id, meta)

    def collect_documents(self, kb_id: str) -> list[tuple[str, str]]:
        """Return ``(label, text)`` for every readable file in this KB."""
        meta = self._load(kb_id)
        documents: list[tuple[str, str]] = []
        raw = self.raw_dir(kb_id)
        for path in _iter_source_files(raw):
            documents.append(
                (path.relative_to(raw).as_posix(), read_text(path, max_bytes=2_000_000))
            )
        for folder in meta.get("linked_folders", []):
            root = Path(str(folder.get("path") or ""))
            if not root.exists():
                continue
            prefix = root.name or "linked"
            for path in _iter_source_files(root):
                documents.append(
                    (
                        f"{prefix}/{path.relative_to(root).as_posix()}",
                        read_text(path, max_bytes=2_000_000),
                    )
                )
        return [(label, text) for label, text in documents if text.strip()]


__all__ = [
    "KnowledgeError",
    "KnowledgeStore",
    "UnknownKnowledgeBase",
    "iso",
]
