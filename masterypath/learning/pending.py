"""Public projection of a pending question (INV-07).

The learner-facing card must never carry ``expected_answer`` or
``explanation``. Everything the model can see about an open question comes
through :func:`public_pending_question`.
"""

from __future__ import annotations

import re
from typing import Any

from masterypath.learning.models import PendingQuestion

# A leading option label: "A: body", "A. body", "A) body", "A、body".
_LABEL_RE = re.compile(r"^\s*([A-Za-z])\s*[:.)、]\s*(.+)$")


def positional_label(index: int) -> str:
    return chr(ord("A") + index)


def parse_options(values: list[str]) -> dict[str, str]:
    """Read option strings into ``{label: body}``.

    Cautious about what counts as a label: ``"x - 1 = 0"`` is *not* option X
    (there is no ``:``/``.``/``)``/``、`` right after the letter). When every
    string carries a label, those labels are used; otherwise labels are
    assigned positionally.
    """
    matches = [_LABEL_RE.match(value) for value in values]
    if all(m is not None for m in matches):
        return {m.group(1).upper(): m.group(2).strip() for m in matches}  # type: ignore[union-attr]
    return {positional_label(i): value.strip() for i, value in enumerate(values)}


def public_pending_question(pending: PendingQuestion) -> dict[str, Any]:
    """Return the learner-safe projection of *pending*."""
    return {
        "question_id": pending.question_id,
        "knowledge_point_id": pending.knowledge_point_id,
        "module_id": pending.module_id,
        "prompt": pending.prompt,
        "question_type": pending.question_type,
        "options": [option.model_dump() for option in pending.options],
        "difficulty": pending.difficulty,
    }


__all__ = ["public_pending_question", "parse_options", "positional_label"]
