"""Knowledge-base operations: settings resolution, indexing, retrieval."""

from __future__ import annotations

import time
from typing import Any, Callable

from masterypath.knowledge import indexer
from masterypath.knowledge.store import (
    KnowledgeError,
    KnowledgeStore,
    UnknownKnowledgeBase,
)
from masterypath.settings import providers as provider_probe
from masterypath.settings.store import SettingsStore

EmbedderFactory = Callable[[dict[str, Any]], indexer.Embedder]


def _default_embedder_factory(config: dict[str, Any]) -> indexer.Embedder:
    protocol = str(config.get("protocol") or "openai")
    base_url = str(config.get("base_url") or "")
    api_key = config.get("api_key")
    model = str(config.get("model") or "")

    def embed(texts: list[str]) -> list[list[float]]:
        return provider_probe.embed_texts(protocol, base_url, api_key, model, texts)

    return embed


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
    def list(self) -> list[dict[str, Any]]:
        return self.store.list()

    def get(self, kb_id: str) -> dict[str, Any]:
        return self.store.get(kb_id)

    def create(
        self,
        name: str,
        *,
        mode: str = "import",
        embedding_model_id: str | None = None,
        description: str = "",
    ) -> dict[str, Any]:
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
            name, mode=mode, embedding_model=embedding, description=description
        )
        if status != "empty":
            meta = self.store.set_index_result(kb_id=meta["id"], status=status, error=error)
        return meta

    def update(self, kb_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        return self.store.update(kb_id, fields)

    def delete(self, kb_id: str) -> None:
        self.store.delete(kb_id)

    def files(self, kb_id: str) -> list[dict[str, Any]]:
        return self.store.files(kb_id)

    def remove_file(self, kb_id: str, rel_path: str) -> None:
        self.store.remove_file(kb_id, rel_path)

    def import_folder(self, kb_id: str, folder: str) -> dict[str, Any]:
        count = self.store.import_folder(kb_id, folder)
        return {"imported": count, **self.reindex(kb_id)}

    def add_linked_folder(self, kb_id: str, folder: str) -> dict[str, Any]:
        entry = self.store.add_linked_folder(kb_id, folder)
        return {"folder": entry, **self.reindex(kb_id)}

    def remove_linked_folder(self, kb_id: str, folder_id: str) -> dict[str, Any]:
        self.store.remove_linked_folder(kb_id, folder_id)
        meta = self.store.get(kb_id)
        if self.store.collect_documents(kb_id):
            return self.reindex(kb_id)
        return self.store.set_index_result(kb_id, status="empty", error="")

    # -- indexing / retrieval ---------------------------------------------
    def reindex(self, kb_id: str) -> dict[str, Any]:
        if not indexer.index_available():
            return self.store.set_index_result(
                kb_id,
                status="rag_prerequisite_missing",
                error="LlamaIndex is not installed. Run: pip install -e \".[rag]\"",
            )
        try:
            config = self.resolve_embedding(
                str(self.store.get(kb_id).get("embedding_model", {}).get("model_id") or "")
            )
        except KnowledgeError as exc:
            return self.store.set_index_result(
                kb_id, status="rag_prerequisite_missing", error=str(exc)
            )
        self.store.set_index_result(kb_id, status="indexing", error="")
        try:
            embedder = self._embedder(config)
            result = indexer.build_index(
                self.store, kb_id, embedder, model_name=config["model"]
            )
        except Exception as exc:  # noqa: BLE001 - report any indexing failure to the UI
            return self.store.set_index_result(kb_id, status="error", error=str(exc))
        embedding = {
            "model_id": config["model_id"],
            "provider_id": config["provider_id"],
            "name": config["name"],
            "model": config["model"],
            "dimension": int(result.get("dimension") or config.get("dimension") or 0),
        }
        return self.store.set_index_result(
            kb_id,
            status="ready",
            error="",
            last_indexed_at=time.time(),
            embedding_model=embedding,
        )

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
