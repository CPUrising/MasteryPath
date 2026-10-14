"""Mastery Path policy — pure decisions over a LearningProgress.

No I/O, no LLM (spec 01 §四, INV-01…05/18/27/28). The gate is the heart:
an objective counts as mastered only when the evidence clears its threshold,
and ``next_objective`` keeps returning the same objective until it does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time

from masterypath.learning.models import (
    AssessmentResult,
    AssessmentType,
    KnowledgePoint,
    KnowledgeType,
    LearningEvidence,
    LearningProgress,
    RepetitionState,
    ReviewTask,
)

# Quantitative gate for MEMORY / PROCEDURE (ADR-007). One named constant.
QUANTITATIVE_GATE: dict[KnowledgeType, float] = {
    KnowledgeType.MEMORY: 0.9,
    KnowledgeType.PROCEDURE: 0.9,
}

# CONCEPT / DESIGN are gated qualitatively (mastery_assess).
QUALITATIVE_TYPES: frozenset[KnowledgeType] = frozenset(
    {KnowledgeType.CONCEPT, KnowledgeType.DESIGN}
)

_QUALITATIVE_PASS_DISPLAY = 1.0


# -- lookup ---------------------------------------------------------------
def find_knowledge_point(
    progress: LearningProgress, kp_id: str
) -> tuple[KnowledgePoint | None, str, str]:
    """Return ``(kp, module_id, module_name)`` or ``(None, "", "")``."""
    for module in progress.modules:
        for kp in module.knowledge_points:
            if kp.id == kp_id:
                return kp, module.id, module.name
    return None, "", ""


def _ordered_modules(progress: LearningProgress):
    return sorted(progress.modules, key=lambda m: m.order)


# -- gate -----------------------------------------------------------------
def gate_threshold(kp_type: KnowledgeType) -> float:
    """Quantitative bar for *kp_type* (qualitative types report pass display)."""
    if kp_type in QUALITATIVE_TYPES:
        return _QUALITATIVE_PASS_DISPLAY
    return QUANTITATIVE_GATE.get(kp_type, 0.9)


def achieved_evidence(progress: LearningProgress, kp_id: str) -> set[str]:
    """Assessment types with a *correct* durable evidence event (INV-28)."""
    return {
        event.assessment_type.value
        for event in progress.learning_evidence
        if event.knowledge_point_id == kp_id
        and event.result == AssessmentResult.CORRECT
    }


def evidence_satisfied(progress: LearningProgress, kp: KnowledgePoint) -> bool:
    """Whether ``kp``'s extra required evidence is present (INV-28)."""
    if not kp.required_evidence:
        return True
    return set(kp.required_evidence).issubset(achieved_evidence(progress, kp.id))


def is_assessed_mastered(progress: LearningProgress, kp: KnowledgePoint) -> bool:
    """Whether ``kp`` clears its mastery gate by evidence alone."""
    if not evidence_satisfied(progress, kp):
        return False
    if kp.type in QUALITATIVE_TYPES:
        return bool(progress.qualitative_mastery.get(kp.id, False))
    return float(progress.mastery_levels.get(kp.id, 0.0)) >= gate_threshold(kp.type)


def mastery_source(progress: LearningProgress, kp: KnowledgePoint) -> str:
    """``system`` | ``learner`` | ``""`` — provenance of a cleared waypoint."""
    if is_assessed_mastered(progress, kp):
        return "system"
    if kp.id in progress.learner_mastery_overrides:
        return "learner"
    return ""


def is_mastered(progress: LearningProgress, kp: KnowledgePoint) -> bool:
    """Whether the route may advance past ``kp`` (INV-03)."""
    return bool(mastery_source(progress, kp))


def display_mastery(progress: LearningProgress, kp: KnowledgePoint) -> float:
    if kp.type in QUALITATIVE_TYPES and progress.qualitative_mastery.get(kp.id):
        return _QUALITATIVE_PASS_DISPLAY
    return float(progress.mastery_levels.get(kp.id, 0.0))


def objective_status(progress: LearningProgress, kp: KnowledgePoint) -> str:
    """``"mastered"`` | ``"learning"`` | ``"new"``."""
    if is_mastered(progress, kp):
        return "mastered"
    seen = any(a.knowledge_point_id == kp.id for a in progress.quiz_attempts) or (
        kp.id in progress.qualitative_mastery
    )
    return "learning" if seen else "new"


def eligible(progress: LearningProgress, kp: KnowledgePoint) -> bool:
    """Whether prerequisites are all mastered (hard gate, INV-27)."""
    for prereq_id in kp.prerequisite_ids:
        prereq, _, _ = find_knowledge_point(progress, prereq_id)
        if prereq is None or not is_mastered(progress, prereq):
            return False
    return True


def active_attempts(progress: LearningProgress, kp_id: str) -> list:
    """Non-voided attempts for *kp_id* (INV-14: voided attempts count for none)."""
    return [
        attempt
        for attempt in progress.quiz_attempts
        if attempt.knowledge_point_id == kp_id and not attempt.voided
    ]


def require_type_unchanged(
    existing: KnowledgePoint, new_type: KnowledgeType | str
) -> None:
    """Refuse a knowledge-point type change (ADR-003 / INV-06).

    Callers that reshape a map must use this before writing a new type; to
    change a type, remove and re-add the objective instead.
    """
    resolved = new_type if isinstance(new_type, KnowledgeType) else KnowledgeType(new_type)
    if resolved is not existing.type:
        raise ValueError(
            "knowledge point type is read-only (ADR-003); remove and re-add the "
            "objective to change it"
        )


# -- review ---------------------------------------------------------------
def due_reviews(
    progress: LearningProgress, *, now: float | None = None
) -> list[ReviewTask]:
    moment = time.time() if now is None else now
    due = [task for task in progress.review_queue if task.due_at <= moment]
    due.sort(key=lambda task: (-task.forgetting_risk, task.due_at))
    return due


# -- navigation -----------------------------------------------------------
@dataclass(frozen=True)
class NextStep:
    """What the tutor should do next, decided by the gate — not a stage cursor."""

    action: str
    module_id: str = ""
    module_name: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    knowledge_point_type: str = ""
    status: str = ""
    mastery: float = 0.0
    threshold: float = 0.0
    reason: str = ""
    pending_prompt: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "module_id": self.module_id,
            "module_name": self.module_name,
            "knowledge_point_id": self.knowledge_point_id,
            "knowledge_point_name": self.knowledge_point_name,
            "knowledge_point_type": self.knowledge_point_type,
            "status": self.status,
            "mastery": self.mastery,
            "threshold": self.threshold,
            "reason": self.reason,
            "pending_prompt": self.pending_prompt,
        }


def next_objective(progress: LearningProgress, *, now: float | None = None) -> NextStep:
    """The single next waypoint, computed from what is mastered (INV-03/27).

    Precedence: an open question first (it needs an answer), then the first
    eligible unmastered objective, then a due review, then complete.
    """
    if progress.pending_question is not None:
        return NextStep(
            action="answer_pending",
            knowledge_point_id=progress.pending_question.knowledge_point_id,
            pending_prompt=progress.pending_question.prompt,
        )

    for module in _ordered_modules(progress):
        for kp in module.knowledge_points:
            if is_mastered(progress, kp):
                continue
            if kp.id in progress.deferred_objectives:
                continue
            if not eligible(progress, kp):
                continue
            action = "assess" if kp.type in QUALITATIVE_TYPES else "practice"
            return NextStep(
                action=action,
                module_id=module.id,
                module_name=module.name,
                knowledge_point_id=kp.id,
                knowledge_point_name=kp.name,
                knowledge_point_type=kp.type.value,
                status=objective_status(progress, kp),
                mastery=display_mastery(progress, kp),
                threshold=gate_threshold(kp.type),
                reason="next eligible objective",
            )

    due = due_reviews(progress, now=now)
    if due:
        task = due[0]
        kp, module_id, module_name = find_knowledge_point(progress, task.knowledge_point_id)
        return NextStep(
            action="review",
            module_id=module_id,
            module_name=module_name,
            knowledge_point_id=task.knowledge_point_id,
            knowledge_point_name=kp.name if kp else "",
            knowledge_point_type=task.knowledge_type.value,
            status="mastered",
            mastery=display_mastery(progress, kp) if kp else 1.0,
            threshold=gate_threshold(task.knowledge_type),
            reason="spaced review due",
        )

    return NextStep(action="complete", reason="every objective mastered")


def map_summary(progress: LearningProgress) -> dict[str, dict]:
    """A per-KP view for the map UI: status / source / mastery / type."""
    summary: dict[str, dict] = {}
    for module in _ordered_modules(progress):
        for kp in module.knowledge_points:
            summary[kp.id] = {
                "name": kp.name,
                "module_id": module.id,
                "module_name": module.name,
                "type": kp.type.value,
                "status": objective_status(progress, kp),
                "source": mastery_source(progress, kp),
                "mastery": display_mastery(progress, kp),
                "threshold": gate_threshold(kp.type),
                "grounding": kp.grounding,
            }
    return summary


__all__ = [
    "QUALITATIVE_TYPES",
    "QUANTITATIVE_GATE",
    "NextStep",
    "achieved_evidence",
    "active_attempts",
    "display_mastery",
    "due_reviews",
    "eligible",
    "evidence_satisfied",
    "find_knowledge_point",
    "gate_threshold",
    "is_assessed_mastered",
    "is_mastered",
    "map_summary",
    "mastery_source",
    "next_objective",
    "objective_status",
    "require_type_unchanged",
]
