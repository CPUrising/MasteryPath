"""Deterministic grading (ADR-008, spec 06 §七).

No LLM is called here: every reference (expected answer, options, keywords,
accepted answers) was fixed at registration. The one rule that matters most:
**an unparseable answer is never graded wrong** — it returns ``ungraded`` so a
guess is not recorded as a negative.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from masterypath.learning.models import PendingQuestion

_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_PUNCT = " \t\r\n。．.，,！!？?；;：:、\"'`()（）[]【】"


@dataclass
class Decision:
    result: str  # "correct" | "incorrect" | "partial" | "ungraded"
    reason: str = ""
    resolved: str = ""


def normalize(text: str) -> str:
    """NFKC -> casefold -> strip -> collapse whitespace -> strip edge punctuation."""
    value = unicodedata.normalize("NFKC", str(text or "")).casefold().strip()
    value = re.sub(r"\s+", " ", value)
    value = value.strip(_PUNCT)
    if _CJK.search(value):
        value = value.replace(" ", "")
    return value


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (ca != cb),
                )
            )
        previous = current
    return previous[-1]


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    longest = max(len(a), len(b))
    if longest == 0:
        return 1.0
    return 1.0 - _levenshtein(a, b) / longest


def _as_number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_choice(answer: str, options: dict[str, str]) -> str:
    """Resolve a learner answer to an option label, or ``""`` when ambiguous."""
    raw = str(answer or "").strip()
    if raw and raw.upper() in options:
        return raw.upper()
    normalized = normalize(raw)
    if not normalized:
        return ""
    matches = [
        label
        for label, body in options.items()
        if normalize(body) == normalized
    ]
    return matches[0] if len(matches) == 1 else ""


def grade(
    pending: PendingQuestion,
    answer: str,
    *,
    short_threshold: float = 0.90,
    open_optional_ratio: float = 0.60,
) -> Decision:
    if pending.question_type == "choice":
        return _grade_choice(pending, answer)
    if pending.question_type == "open":
        return _grade_open(pending, answer, open_optional_ratio)
    return _grade_short(pending, answer, short_threshold)


def _grade_choice(pending: PendingQuestion, answer: str) -> Decision:
    options = pending.choice_map
    label = resolve_choice(answer, options)
    if not label:
        shown = "; ".join(f"{k} = {v}" for k, v in options.items())
        return Decision(
            result="ungraded",
            reason=f"could not tell which option {answer!r} picks; options: {shown}",
        )
    if label == pending.expected_answer:
        return Decision(result="correct", resolved=label)
    return Decision(result="incorrect", resolved=label)


def _grade_short(pending: PendingQuestion, answer: str, threshold: float) -> Decision:
    expected = pending.expected_answer
    learner = normalize(answer)
    target = normalize(expected)
    if not learner:
        return Decision(result="ungraded", reason="empty answer")
    if learner == target:
        return Decision(result="correct", reason="exact")
    if any(learner == normalize(a) for a in pending.accepted_answers):
        return Decision(result="correct", reason="accepted equivalent")
    left, right = _as_number(learner), _as_number(target)
    if left is not None and right is not None:
        if abs(left - right) <= 1e-6 * max(1.0, abs(right)):
            return Decision(result="correct", reason="numeric")
        return Decision(result="incorrect", reason="numeric mismatch")
    # Long answers only match exactly (avoid noisy fuzzy matches).
    if len(target) > 30 or len(learner) > 30:
        return Decision(result="incorrect", reason="too long for fuzzy")
    if similarity(learner, target) >= threshold:
        return Decision(result="correct", reason="fuzzy")
    return Decision(result="incorrect", reason="below fuzzy threshold")


def _grade_open(
    pending: PendingQuestion, answer: str, optional_ratio: float
) -> Decision:
    text = normalize(answer)
    required = [normalize(k) for k in pending.required_keywords if k]
    optional = [normalize(k) for k in pending.optional_keywords if k]
    if not text:
        return Decision(result="ungraded", reason="empty answer")
    if not required and not optional:
        # No keywords fixed => cannot judge understanding deterministically.
        return Decision(result="ungraded", reason="no keywords registered")
    required_hit = [k for k in required if k in text]
    optional_hit = [k for k in optional if k in text]
    if len(required_hit) < len(required):
        return Decision(result="partial" if required_hit else "incorrect", reason="missing required")
    if optional and len(optional_hit) / len(optional) < optional_ratio:
        return Decision(result="partial", reason="optional keywords below ratio")
    return Decision(result="correct", reason="keywords satisfied")


__all__ = ["Decision", "grade", "normalize", "resolve_choice", "similarity"]
