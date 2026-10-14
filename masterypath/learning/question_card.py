"""Question card — the learner-facing projection (spec 06 §五, INV-07).

The card the learner answers carries only public fields; ``expected_answer``
and ``explanation`` never appear here.
"""

from __future__ import annotations

from typing import Any

from masterypath.learning.models import LearningProgress, PendingQuestion
from masterypath.learning.pending import public_pending_question

QUESTION_CARD_KEY = "question_card"


def attempt_number(progress: LearningProgress, kp_id: str) -> int:
    return sum(1 for a in progress.quiz_attempts if a.knowledge_point_id == kp_id) + 1


def build_question_card(
    pending: PendingQuestion, *, objective_name: str = "", attempt: int = 1
) -> dict[str, Any]:
    card = public_pending_question(pending)
    card["objective_name"] = objective_name
    card["attempt"] = attempt
    return card


__all__ = ["QUESTION_CARD_KEY", "attempt_number", "build_question_card"]
