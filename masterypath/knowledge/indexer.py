"""LlamaIndex vector retrieval for knowledge bases.

The embedding provider is resolved from settings by the caller and passed in as
a plain ``embedder(texts) -> vectors`` callable. That keeps LlamaIndex unaware
of our provider protocols and lets tests run offline with a deterministic
embedder.

On Python 3.14 the BM25 retriever is unavailable (PyStemmer has no wheels), so
retrieval is vector-only, matching DeepTutor's current environment.
"""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
import shutil
from typing import Any, Callable

from masterypath.knowledge.store import KnowledgeStore

Embedder = Callable[[list[str]], list[list[float]]]

try:  # pragma: no cover - exercised by the availability test
    from llama_index.core import (
        Document,
        StorageContext,
        VectorStoreIndex,
        load_index_from_storage,
    )
    from llama_index.core.embeddings import BaseEmbedding
    from llama_index.core.node_parser import SentenceSplitter
    from pydantic import PrivateAttr

    LLAMA_AVAILABLE = True
    LLAMA_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - missing optional dependency
    LLAMA_AVAILABLE = False
    LLAMA_IMPORT_ERROR = str(exc)


class IndexUnavailable(RuntimeError):
    """LlamaIndex (or the embedding provider) is not usable."""


def index_available() -> bool:
    return LLAMA_AVAILABLE


if LLAMA_AVAILABLE:

    class ProviderEmbedding(BaseEmbedding):  # type: ignore[misc]
        """Adapter from a provider embedder callable to a LlamaIndex embedding."""

        _embedder: Embedder = PrivateAttr()

        def __init__(self, embedder: Embedder, model_name: str = "") -> None:
            super().__init__(model_name=model_name)
            self._embedder = embedder

        @classmethod
        def class_name(cls) -> str:
            return "ProviderEmbedding"

        def _get_query_embedding(self, query: str) -> list[float]:
            return self._embedder([query])[0]

        def _get_text_embedding(self, text: str) -> list[float]:
            return self._embedder([text])[0]

        def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
            return self._embedder(texts)

        async def _aget_query_embedding(self, query: str) -> list[float]:
            return await asyncio.to_thread(self._get_query_embedding, query)

        async def _aget_text_embedding(self, text: str) -> list[float]:
            return await asyncio.to_thread(self._get_text_embedding, text)


def _probe_dimension(embedder: Embedder) -> int:
    vector = embedder(["dimension probe"])[0]
    return len(vector)


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_index(
    store: KnowledgeStore,
    kb_id: str,
    embedder: Embedder,
    *,
    model_name: str = "",
) -> dict[str, Any]:
    """Chunk, embed, and persist a vector index for one knowledge base."""
    if not LLAMA_AVAILABLE:
        raise IndexUnavailable(
            "LlamaIndex is not installed. Run: pip install -e \".[rag]\""
        )
    documents = store.collect_documents(kb_id)
    if not documents:
        raise IndexUnavailable("This knowledge base has no readable documents yet.")

    index_dir = store.index_dir(kb_id)
    if index_dir.exists():
        shutil.rmtree(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    embedding = ProviderEmbedding(embedder, model_name=model_name)
    splitter = SentenceSplitter(chunk_size=800, chunk_overlap=100)
    docs = [
        Document(text=text, metadata={"source": label})
        for label, text in documents
    ]
    storage_context = StorageContext.from_defaults()
    index = VectorStoreIndex.from_documents(
        docs,
        storage_context=storage_context,
        embed_model=embedding,
        transformations=[splitter],
        show_progress=False,
    )
    storage_context.persist(persist_dir=str(index_dir))
    return {
        "documents": len(documents),
        "chunks": len(index.docstore.docs),
        "dimension": _probe_dimension(embedder),
    }


def load_index(store: KnowledgeStore, kb_id: str, embedder: Embedder):
    if not LLAMA_AVAILABLE:
        raise IndexUnavailable(
            "LlamaIndex is not installed. Run: pip install -e \".[rag]\""
        )
    index_dir = store.index_dir(kb_id)
    if not index_dir.exists() or not any(index_dir.iterdir()):
        raise IndexUnavailable("This knowledge base has not been indexed yet.")
    storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
    return load_index_from_storage(
        storage_context,
        embed_model=ProviderEmbedding(embedder),
    )


def search(
    store: KnowledgeStore,
    kb_id: str,
    query: str,
    embedder: Embedder,
    *,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return the top matching chunks with their source labels."""
    if not (query or "").strip():
        return []
    index = load_index(store, kb_id, embedder)
    nodes = index.as_retriever(similarity_top_k=max(1, int(top_k))).retrieve(query)
    results = []
    for node in nodes:
        results.append(
            {
                "text": node.get_content(),
                "source": str(node.metadata.get("source") or ""),
                "score": float(node.score or 0.0),
            }
        )
    return results


__all__ = [
    "Embedder",
    "IndexUnavailable",
    "LLAMA_AVAILABLE",
    "LLAMA_IMPORT_ERROR",
    "build_index",
    "index_available",
    "load_index",
    "search",
]
