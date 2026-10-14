"""Mastery level from attempts — recency-weighted accuracy (ADR-007).

Pure. The quantitative gate reads this number; concept/design ignore it.
"""

from __future__ import annotations

from masterypath.learning.models import QuizAttempt

# More recent attempts weigh more, so a learner who has improved is not held
# down by early mistakes forever.
_DECAY = 0.6


def compute_mastery(attempts: list[QuizAttempt]) -> float:
    """Recency-weighted accuracy over non-voided attempts (0.0 when none)."""
    active = [a for a in attempts if not a.voided]
    if not active:
        return 0.0
    total = 0.0
    weight_sum = 0.0
    count = len(active)
    for index, attempt in enumerate(active):
        # index 0 is the oldest; newest gets weight 1.0
        rank = count - 1 - index
        weight = _DECAY**rank
        total += weight * (1.0 if attempt.is_correct else 0.0)
        weight_sum += weight
    return total / weight_sum if weight_sum else 0.0


__all__ = ["compute_mastery"]
