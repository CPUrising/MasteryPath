"""Learning service — the seam between callers (tools / REST) and the store.

Wraps pure outline transforms in ``store.mutate`` so state + events commit
together (INV-51). Knows nothing about LLMs (ADR-014).
"""

from __future__ import annotations

from typing import Any

from masterypath.learning import policy
from masterypath.learning.models import (
    KnowledgeType,
    LearnerMasteryOverride,
    LearningProgress,
)
from masterypath.learning.outline import (
    BuildResult,
    ReviseResult,
    build_outline,
    resolve_gap,
    revise_outline,
)
from masterypath.learning.storage import LearningStore


class LearningService:
    def __init__(
        self,
        store: LearningStore,
        *,
        source_map: dict[str, str] | None = None,
        selected_source_ids: set[str] | None = None,
    ) -> None:
        self.store = store
        self.source_map = source_map
        self.selected_source_ids = selected_source_ids

    # -- lifecycle ---------------------------------------------------------
    def create_path(
        self, path_id: str, *, goal: str = "", name: str = ""
    ) -> LearningProgress:
        progress = LearningProgress(path_id=path_id, goal=goal, name=name)
        return self.store.create(progress)

    def get_state(self, path_id: str) -> dict[str, Any]:
        progress = self.store.load(path_id)
        if progress is None:
            return {"status": "missing", "path_id": path_id}
        step = policy.next_objective(progress)
        return {
            "status": "active",
            "path_id": path_id,
            "name": progress.name,
            "goal": progress.goal,
            "version": progress.version,
            "map": policy.map_summary(progress),
            "next": step.to_dict(),
            "gaps": [gap.model_dump() for gap in progress.source_gaps],
            "pending_question": progress.pending_question
            and _public(progress.pending_question),
            "due_reviews": [task.model_dump() for task in policy.due_reviews(progress)],
        }

    # -- outline -----------------------------------------------------------
    def build(
        self,
        path_id: str,
        payload: dict[str, Any],
        *,
        confirm: bool = False,
        session_id: str = "",
        turn_id: str = "",
    ) -> BuildResult:
        def fn(tx):
            result = build_outline(
                tx.progress,
                payload,
                confirm=confirm,
                source_map=self.source_map,
                selected_source_ids=self.selected_source_ids,
            )
            if result.status == "built":
                event_type = "path.rebuilt" if result.rebuilt else "outline.built"
                tx.emit(
                    event_type,
                    {
                        "module_count": len(result.modules),
                        "gap_ids": [gap.id for gap in result.gaps],
                    },
                )
            return result

        return self.store.mutate(path_id, fn, create_if_missing=True)

    def revise(
        self,
        path_id: str,
        ops: list[dict[str, Any]],
        *,
        session_id: str = "",
        turn_id: str = "",
    ) -> ReviseResult:
        def fn(tx):
            result = revise_outline(
                tx.progress, ops, selected_source_ids=self.selected_source_ids
            )
            tx.emit(
                "outline.revised",
                {
                    "applied": result.applied,
                    "dropped_kp_ids": result.dropped_kp_ids,
                },
            )
            return result

        return self.store.mutate(path_id, fn)

    def resolve_gap(self, path_id: str, gap_id: str, action: str):
        def fn(tx):
            gap = resolve_gap(tx.progress, gap_id, action)
            tx.emit("gap.resolved", {"gap_id": gap_id, "action": action})
            return gap

        return self.store.mutate(path_id, fn)

    def override_mastery(self, path_id: str, kp_id: str, note: str = ""):
        """Learner declares mastery: advances frontier, writes no score (INV-01)."""

        def fn(tx):
            kp, _ = tx.progress.find_knowledge_point(kp_id)
            tx.require(kp is not None, f"unknown knowledge point: {kp_id}")
            assert kp is not None
            tx.progress.learner_mastery_overrides[kp_id] = LearnerMasteryOverride(
                knowledge_point_id=kp_id, note=note
            )
            tx.emit("mastery.override", {"knowledge_point_id": kp_id, "note": note})
            return {"knowledge_point_id": kp_id, "source": "learner"}

        return self.store.mutate(path_id, fn)


def _public(pending) -> dict[str, Any]:
    from masterypath.learning.pending import public_pending_question

    return public_pending_question(pending)


__all__ = ["LearningService"]
