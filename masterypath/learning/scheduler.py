"""Spaced-repetition scheduling — SM-2 (ADR-009, spec 04).

Pure arithmetic. One scheduler, seeded by provenance (ADR-002): a declared
mastery starts with a shorter first interval than an assessed one.

``scheduled_after_failure`` marks that the *anchor* (``next_review_at``) was
set in response to a lapse. It follows the anchor: a real review success sets
a new anchor and clears it; in-session practice only touches ``last_review_at``
and never moves it (INV-29/30).
"""

from __future__ import annotations

import time

from masterypath.learning.models import (
    KnowledgePoint,
    LearningProgress,
    RepetitionState,
    ReviewTask,
)

SECONDS_PER_DAY = 86400.0
RELEARNING_SECONDS = 600.0  # 10 minutes
DEFAULT_EF = 2.5
MIN_EF = 1.3
LEARNER_FIRST_FACTOR = 0.5  # declared mastery starts ~half the interval


def quality_from_result(result: str, hints_used: int = 0) -> int:
    """Map our grading result to SM-2's q (0..5)."""
    if result == "correct" and hints_used == 0:
        return 5
    if result == "correct":
        return 4
    if result == "partial":
        return 3
    return 0


def update_ease(ease_factor: float, quality: int) -> float:
    adjusted = ease_factor + (
        0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    )
    return max(MIN_EF, adjusted)


def interval_days(index: int, ease_factor: float) -> int:
    """SM-2 interval: 1, 6, then previous * EF."""
    if index <= 1:
        return 1
    if index == 2:
        return 6
    days = 6.0
    for _ in range(3, index + 1):
        days = round(days * ease_factor)
    return int(days)


def initial_state(
    *, provenance: str, now: float | None = None, desired_retention: float = 0.9
) -> RepetitionState:
    """Seed a freshly-mastered objective (single scheduler, provenance-seeded)."""
    moment = time.time() if now is None else now
    factor = LEARNER_FIRST_FACTOR if provenance == "learner" else 1.0
    first = interval_days(1, DEFAULT_EF) * factor
    return RepetitionState(
        interval_index=1,
        ease_factor=DEFAULT_EF,
        next_review_at=moment + first * SECONDS_PER_DAY,
        last_scheduled_at=moment,
        provenance=provenance if provenance in ("system", "learner") else "system",
        desired_retention=desired_retention,
    )


def apply_review(
    state: RepetitionState,
    *,
    result: str,
    hints_used: int = 0,
    now: float | None = None,
) -> RepetitionState:
    """Update a repetition state after a review outcome (mutates in place)."""
    moment = time.time() if now is None else now
    quality = quality_from_result(result, hints_used)
    state.ease_factor = update_ease(state.ease_factor, quality)
    state.review_count += 1
    state.last_review_at = moment
    if quality < 3:
        # Lapse: back to relearning; the anchor was set by a failure.
        state.interval_index = 0
        state.consecutive_correct = 0
        state.consecutive_wrong += 1
        state.lapse_count += 1
        state.next_review_at = moment + RELEARNING_SECONDS
        state.last_scheduled_at = moment
        state.scheduled_after_failure = True
    else:
        state.interval_index += 1
        state.consecutive_correct += 1
        state.consecutive_wrong = 0
        state.next_review_at = (
            moment + interval_days(state.interval_index, state.ease_factor) * SECONDS_PER_DAY
        )
        state.last_scheduled_at = moment
        state.scheduled_after_failure = False
    return state


def touch_last_review(state: RepetitionState, *, now: float | None = None) -> RepetitionState:
    """In-session practice: update ``last_review_at`` only (INV-29)."""
    state.last_review_at = time.time() if now is None else now
    return state


def build_review_task(
    kp: KnowledgePoint,
    state: RepetitionState,
    *,
    reason: str = "spaced review",
    evidence_source: str = "",
    evidence_id: str = "",
) -> ReviewTask:
    return ReviewTask(
        id=f"rev:{kp.id}",
        knowledge_point_id=kp.id,
        knowledge_type=kp.type,
        due_at=state.next_review_at,
        state=state,
        reason=reason,
        evidence_source=evidence_source,
        evidence_id=evidence_id,
    )


def upsert_review_task(
    progress: LearningProgress,
    kp: KnowledgePoint,
    state: RepetitionState,
    **kwargs,
) -> ReviewTask:
    task = build_review_task(kp, state, **kwargs)
    progress.review_queue = [
        existing for existing in progress.review_queue if existing.knowledge_point_id != kp.id
    ]
    progress.review_queue.append(task)
    return task


__all__ = [
    "DEFAULT_EF",
    "LEARNER_FIRST_FACTOR",
    "MIN_EF",
    "RELEARNING_SECONDS",
    "SECONDS_PER_DAY",
    "apply_review",
    "build_review_task",
    "initial_state",
    "interval_days",
    "quality_from_result",
    "touch_last_review",
    "update_ease",
    "upsert_review_task",
]
