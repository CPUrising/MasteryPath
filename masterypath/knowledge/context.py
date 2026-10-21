"""Build the reference block injected before a turn from the learner's KBs."""

from __future__ import annotations

from typing import Any, Iterable


def knowledge_context(
    knowledge_service: Any,
    kb_ids: Iterable[str],
    query: str,
    *,
    top_k: int = 4,
) -> str:
    """Return a "Reference material" block, or ``""`` when nothing was found.

    Retrieval is best-effort: an unready or unreachable knowledge base is
    skipped rather than failing the turn.
    """
    if knowledge_service is None or not query.strip():
        return ""
    blocks: list[str] = []
    for kb_id in kb_ids:
        try:
            hits = knowledge_service.search(str(kb_id), query, top_k=top_k)
        except Exception:  # noqa: BLE001 - retrieval must never break a turn
            hits = []
        if not hits:
            continue
        try:
            name = str(knowledge_service.get(str(kb_id)).get("name") or kb_id)
        except Exception:  # noqa: BLE001
            name = str(kb_id)
        joined = "\n\n".join(
            f"[{hit.get('source') or 'source'}]\n{hit.get('text', '')}" for hit in hits
        )
        blocks.append(f"# {name}\n{joined}")
    if not blocks:
        return ""
    return "Reference material:\n\n" + "\n\n".join(blocks)


__all__ = ["knowledge_context"]
