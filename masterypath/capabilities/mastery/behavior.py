"""Tutor behavior budgets (ADR-019 / INV-60).

Values are confirmed defaults (see `docs/00` §四 #11). Kept here so the loop,
the tools and the tests read one source.
"""

from __future__ import annotations

MAX_TOOL_CALLS_PER_TURN = 6
MAX_CONSECUTIVE_QUESTIONS = 3
MAX_HINTS_PER_QUESTION = 2

__all__ = [
    "MAX_CONSECUTIVE_QUESTIONS",
    "MAX_HINTS_PER_QUESTION",
    "MAX_TOOL_CALLS_PER_TURN",
]
