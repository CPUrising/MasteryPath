"""Test factories for building path aggregates."""

from __future__ import annotations

from masterypath.learning.models import (
    KnowledgePoint,
    KnowledgeType,
    LearningModule,
    LearningProgress,
)


def kp(
    kp_id: str,
    name: str,
    kp_type: KnowledgeType = KnowledgeType.CONCEPT,
    module_id: str = "m1",
    prereq: list[str] | None = None,
    sources: list[str] | None = None,
) -> KnowledgePoint:
    return KnowledgePoint(
        id=kp_id,
        name=name,
        type=kp_type,
        module_id=module_id,
        prerequisite_ids=prereq or [],
        source_ids=["s1"] if sources is None else sources,
    )


def module(
    module_id: str,
    name: str,
    order: int,
    kps: list[KnowledgePoint],
    objective: str = "",
    display_target: float = 0.7,
) -> LearningModule:
    return LearningModule(
        id=module_id,
        name=name,
        order=order,
        objective=objective,
        display_target=display_target,
        knowledge_points=kps,
    )


def progress(modules: list[LearningModule], path_id: str = "p1", **kw) -> LearningProgress:
    return LearningProgress(path_id=path_id, modules=modules, **kw)
