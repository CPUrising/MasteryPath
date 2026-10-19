"""Knowledge-base operations: settings resolution, indexing, retrieval."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable
import uuid

from masterypath.knowledge import indexer
from masterypath.knowledge.store import (
    KnowledgeError,
    KnowledgeStore,
    UnknownKnowledgeBase,
)
from masterypath.settings import providers as provider_probe
from masterypath.settings.store import SettingsStore

EmbedderFactory = Callable[[dict[str, Any]], indexer.Embedder]

#: Allowed chunking values (token units). The frontend mirrors these but the
#: backend is the authority.
CHUNK_SIZE_CHOICES: tuple[int, ...] = (512, 800, 1024, 1536)
CHUNK_OVERLAP_CHOICES: tuple[int, ...] = (0, 64, 100, 128, 200)
DEFAULT_INDEX_CONFIG: dict[str, Any] = {"chunk_size": 512, "chunk_overlap": 64}
TOKENIZER_TAG = "tiktoken/cl100k_base"


def normalize_chunk_config(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        raise KnowledgeError("Chunk settings must be an object.")
    try:
        size = int(value.get("chunk_size"))
        overlap = int(value.get("chunk_overlap"))
    except (TypeError, ValueError) as exc:
        raise KnowledgeError("Chunk size and overlap must be whole numbers.") from exc
    if size not in CHUNK_SIZE_CHOICES:
        raise KnowledgeError(f"chunk_size must be one of {list(CHUNK_SIZE_CHOICES)}.")
    if overlap not in CHUNK_OVERLAP_CHOICES:
        raise KnowledgeError(f"chunk_overlap must be one of {list(CHUNK_OVERLAP_CHOICES)}.")
    if not 0 <= overlap < size:
        raise KnowledgeError("chunk_overlap must be smaller than chunk_size.")
    return {"chunk_size": size, "chunk_overlap": overlap}


def _default_embedder_factory(config: dict[str, Any]) -> indexer.Embedder:
    protocol = str(config.get("protocol") or "openai")
    base_url = str(config.get("base_url") or "")
    api_key = config.get("api_key")
    model = str(config.get("model") or "")

    def embed(texts: list[str]) -> list[list[float]]:
        return provider_probe.embed_texts(protocol, base_url, api_key, model, texts)

    return embed


def _percent(entry: dict[str, Any]) -> float | None:
    """``indexed / total`` as the UI shows it; ``None`` when total is unknown."""
    total = int(entry.get("total_files") or 0)
    if total <= 0:
        return None
    indexed = int(entry.get("indexed_files") or 0)
    return max(0.0, min(1.0, indexed / total))


class KnowledgeService:
    def __init__(
        self,
        store: KnowledgeStore,
        settings: SettingsStore,
        *,
        embedder_factory: EmbedderFactory | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self._embedder_factory = embedder_factory or _default_embedder_factory
        self._lock = threading.Lock()
        self._progress: dict[str, dict[str, Any]] = {}

    # -- embedding resolution ---------------------------------------------
    def resolve_embedding(self, model_id: str | None = None) -> dict[str, Any]:
        """Resolve one configured embedding model to a callable provider config."""
        section = self.settings.section("embedding")
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
            raise KnowledgeError(
                "No embedding model is configured. Add one under Settings → Embedding."
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
            raise KnowledgeError(
                "The embedding model's provider is missing a base URL. "
                "Check Settings → Providers."
            )
        return {
            "model_id": str(chosen.get("id") or ""),
            "provider_id": provider_id,
            "name": str(chosen.get("name") or chosen.get("model") or ""),
            "model": str(chosen.get("model") or ""),
            "dimension": int(chosen.get("dimension") or 0),
            "protocol": str(provider.get("protocol") or "openai"),
            "base_url": str(provider.get("base_url") or ""),
            "api_key": provider.get("api_key") or "",
        }

    def _embedder(self, config: dict[str, Any]) -> indexer.Embedder:
        return self._embedder_factory(config)

    # -- CRUD --------------------------------------------------------------
    def global_index_config(self) -> dict[str, int]:
        try:
            return normalize_chunk_config(self.settings.section("indexing"))
        except KnowledgeError:
            return dict(DEFAULT_INDEX_CONFIG)

    def effective_config(self, meta: dict[str, Any]) -> dict[str, int]:
        override = meta.get("index_config") or {}
        if override:
            try:
                return normalize_chunk_config(override)
            except KnowledgeError:
                pass
        return self.global_index_config()

    def _decorate(self, meta: dict[str, Any]) -> dict[str, Any]:
        effective = self.effective_config(meta)
        indexed = meta.get("indexed_config") or {}
        meta["effective_config"] = effective
        meta["index_config_source"] = "kb" if (meta.get("index_config") or {}) else "global"
        # Legacy KBs indexed before snapshots existed have no comparable record.
        same = indexed.get("chunk_size") == effective["chunk_size"] and indexed.get(
            "chunk_overlap"
        ) == effective["chunk_overlap"]
        meta["needs_reindex"] = bool(indexed) and not same
        return meta

    def list(self) -> list[dict[str, Any]]:
        return [self._decorate(meta) for meta in self.store.list()]

    def get(self, kb_id: str) -> dict[str, Any]:
        return self._decorate(self.store.get(kb_id))

    def create(
        self,
        name: str,
        *,
        mode: str = "import",
        embedding_model_id: str | None = None,
        description: str = "",
        index_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validated = normalize_chunk_config(index_config) if index_config else {}
        try:
            config = self.resolve_embedding(embedding_model_id)
            embedding = {
                "model_id": config["model_id"],
                "provider_id": config["provider_id"],
                "name": config["name"],
                "model": config["model"],
                "dimension": config["dimension"],
            }
            status = "empty"
            error = ""
        except KnowledgeError as exc:
            embedding = {}
            status = "rag_prerequisite_missing"
            error = str(exc)
        meta = self.store.create(
            name,
            mode=mode,
            embedding_model=embedding,
            description=description,
            index_config=validated,
        )
        if status != "empty":
            meta = self.store.set_index_result(kb_id=meta["id"], status=status, error=error)
        return self._decorate(meta)

    def update(self, kb_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        payload = dict(fields)
        if "index_config" in payload and payload["index_config"]:
            payload["index_config"] = normalize_chunk_config(payload["index_config"])
        return self._decorate(self.store.update(kb_id, payload))

    def delete(self, kb_id: str) -> None:
        self.store.delete(kb_id)
        with self._lock:
            self._progress.pop(kb_id, None)

    def files(self, kb_id: str) -> list[dict[str, Any]]:
        return self.store.files(kb_id)

    def remove_file(self, kb_id: str, rel_path: str) -> None:
        self.store.remove_file(kb_id, rel_path)

    # -- ingestion ---------------------------------------------------------
    def upload(
        self,
        kb_id: str,
        uploads: list[tuple[str, bytes]],
        *,
        conflict: str = "overwrite",
        background: bool = True,
    ) -> dict[str, Any]:
        written = self.store.write_uploads(kb_id, uploads, conflict=conflict)
        result = self.reindex(kb_id, background=background)
        return {"uploaded": written, **result}

    def import_folder(
        self, kb_id: str, folder: str, *, background: bool = True
    ) -> dict[str, Any]:
        count = self.store.import_folder(kb_id, folder)
        return {"imported": count, **self.reindex(kb_id, background=background)}

    def add_linked_folder(
        self, kb_id: str, folder: str, *, background: bool = True
    ) -> dict[str, Any]:
        entry = self.store.add_linked_folder(kb_id, folder)
        return {"folder": entry, **self.reindex(kb_id, background=background)}

    def remove_linked_folder(self, kb_id: str, folder_id: str) -> dict[str, Any]:
        self.store.remove_linked_folder(kb_id, folder_id)
        if self.store.collect_documents(kb_id):
            return self.reindex(kb_id)
        return self.store.set_index_result(kb_id, status="empty", error="")

    # -- progress ----------------------------------------------------------
    def _current_run(self, kb_id: str) -> str:
        with self._lock:
            entry = self._progress.get(kb_id)
            return str(entry.get("run_id") or "") if entry else ""

    def _update_progress(self, kb_id: str, run_id: str, **fields: Any) -> None:
        with self._lock:
            entry = self._progress.get(kb_id)
            if entry is None or entry.get("run_id") != run_id:
                return
            entry.update(fields)
            entry["updated_at"] = time.time()

    def progress(self, kb_id: str) -> dict[str, Any]:
        self.store.get(kb_id)  # 404 when missing
        with self._lock:
            entry = dict(self._progress[kb_id]) if kb_id in self._progress else None
        if entry is not None:
            entry["percent"] = _percent(entry)
            return entry
        meta = self.store.get(kb_id)
        status = str(meta.get("status") or "empty")
        return {
            "run_id": "",
            "status": status,
            "phase": "idle",
            "indexed_files": 0,
            "total_files": int(meta.get("doc_count") or 0),
            "chunks": int(meta.get("chunk_count") or 0),
            "error": str(meta.get("error") or ""),
            "started_at": 0,
            "updated_at": float(meta.get("updated_at") or 0),
            "percent": 1.0 if status == "ready" else None,
        }

    # -- indexing ----------------------------------------------------------
    def reindex(self, kb_id: str, *, background: bool = True) -> dict[str, Any]:
        self.store.get(kb_id)
        with self._lock:
            existing = self._progress.get(kb_id)
            if existing and existing.get("status") == "indexing":
                snapshot = dict(existing)
                snapshot["percent"] = _percent(snapshot)
                return snapshot
            run_id = uuid.uuid4().hex

        if not indexer.index_available():
            self.store.set_index_result(
                kb_id,
                status="rag_prerequisite_missing",
                error="LlamaIndex is not installed. Run: pip install -e \".[rag]\"",
            )
            return self.store.get(kb_id)
        try:
            config = self.resolve_embedding(
                str(self.store.get(kb_id).get("embedding_model", {}).get("model_id") or "")
            )
        except KnowledgeError as exc:
            self.store.set_index_result(
                kb_id, status="rag_prerequisite_missing", error=str(exc)
            )
            return self.store.get(kb_id)

        documents = self.store.collect_documents(kb_id)
        if not documents:
            self.store.set_index_result(kb_id, status="empty", error="")
            with self._lock:
                self._progress[kb_id] = {
                    "run_id": run_id,
                    "status": "empty",
                    "phase": "idle",
                    "indexed_files": 0,
                    "total_files": 0,
                    "chunks": 0,
                    "error": "",
                    "started_at": time.time(),
                    "updated_at": time.time(),
                }
            return self.store.get(kb_id) if not background else {
                "status": "empty",
                "total_files": 0,
                "run_id": run_id,
            }

        with self._lock:
            self._progress[kb_id] = {
                "run_id": run_id,
                "status": "indexing",
                "phase": "scanning",
                "indexed_files": 0,
                "total_files": len(documents),
                "chunks": 0,
                "error": "",
                "started_at": time.time(),
                "updated_at": time.time(),
            }
        self.store.set_index_result(kb_id, status="indexing", error="")
        chunk = self.effective_config(self.store.get(kb_id))

        if background:
            threading.Thread(
                target=self._run_index,
                args=(kb_id, config, run_id, len(documents), chunk),
                daemon=True,
            ).start()
            return {"status": "indexing", "total_files": len(documents), "run_id": run_id}
        self._run_index(kb_id, config, run_id, len(documents), chunk)
        return self.store.get(kb_id)

    def _run_index(
        self,
        kb_id: str,
        config: dict[str, Any],
        run_id: str,
        total: int,
        chunk: dict[str, int],
    ) -> None:
        try:
            embedder = self._embedder(config)

            def on_progress(indexed: int, count: int) -> None:
                self._update_progress(
                    kb_id,
                    run_id,
                    indexed_files=indexed,
                    total_files=count,
                    phase="embedding",
                )

            result = indexer.build_index(
                self.store,
                kb_id,
                embedder,
                model_name=config["model"],
                on_progress=on_progress,
                chunk_size=chunk["chunk_size"],
                chunk_overlap=chunk["chunk_overlap"],
            )
        except Exception as exc:  # noqa: BLE001 - report any indexing failure to the UI
            if self._current_run(kb_id) == run_id:
                self.store.set_index_result(kb_id, status="error", error=str(exc))
                self._update_progress(
                    kb_id, run_id, status="error", error=str(exc), phase="idle"
                )
            return

        if self._current_run(kb_id) != run_id:
            # A newer run replaced this one; discard the stale result.
            return
        embedding = {
            "model_id": config["model_id"],
            "provider_id": config["provider_id"],
            "name": config["name"],
            "model": config["model"],
            "dimension": int(result.get("dimension") or config.get("dimension") or 0),
        }
        self.store.set_index_result(
            kb_id,
            status="ready",
            error="",
            last_indexed_at=time.time(),
            embedding_model=embedding,
            chunk_count=int(result.get("chunks") or 0),
            indexed_config={
                "chunk_size": chunk["chunk_size"],
                "chunk_overlap": chunk["chunk_overlap"],
                "tokenizer": TOKENIZER_TAG,
            },
        )
        self._update_progress(
            kb_id,
            run_id,
            status="ready",
            phase="persisting",
            indexed_files=total,
            total_files=total,
            chunks=int(result.get("chunks") or 0),
        )

    # -- retrieval ---------------------------------------------------------
    def search(self, kb_id: str, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        meta = self.store.get(kb_id)
        if meta.get("status") != "ready":
            return []
        config = meta.get("embedding_model") or {}
        try:
            resolved = self.resolve_embedding(str(config.get("model_id") or ""))
        except KnowledgeError:
            return []
        try:
            return indexer.search(
                self.store, kb_id, query, self._embedder(resolved), top_k=top_k
            )
        except Exception:  # noqa: BLE001 - retrieval failure must not break chat
            return []


__all__ = ["EmbedderFactory", "KnowledgeError", "KnowledgeService", "UnknownKnowledgeBase"]
