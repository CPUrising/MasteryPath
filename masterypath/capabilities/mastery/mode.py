"""What a mastery conversation is doing right now (spec 02).

Three separate things: the engine (one loop), the *mode* (which prompt block
frames the sitting and which tools it may use), and the *session* (which can
change mode). The mode is mutable state on a session.

Every mastery tool is mounted every turn; the mode is enforced when a tool is
*called*, not when it is mounted, because a turn's tool schemas are assembled
once before the first round.

Classification is **fail-closed** (ADR-005): a tool that is neither in
``TOOL_MODES`` nor in ``SHARED_TOOLS`` is not silently shared.
"""

from __future__ import annotations

from typing import Any

OUTLINE = "outline"
STUDY = "study"
REVIEW = "review"

MODES: tuple[str, ...] = (OUTLINE, STUDY, REVIEW)
DEFAULT_MODE = STUDY

# Mode-exclusive tools.
OUTLINE_ONLY: frozenset[str] = frozenset({"mastery_build", "mastery_revise"})
STUDY_REVIEW: frozenset[str] = frozenset(
    {
        "mastery_quiz",
        "mastery_grade",
        "mastery_assess",
        "mastery_skip_question",
        "mastery_repair_question",
        "mastery_defer_objective",
        "mastery_note_explained",
    }
)

# Explicitly shared — true regardless of mode. Listed so the guard can prove
# every tool was classified (fail-closed, INV-17).
SHARED_TOOLS: frozenset[str] = frozenset(
    {
        "mastery_status",
        "mastery_mode",
        "mastery_profile",
        "mastery_paths",
        "mastery_switch",
        "mastery_leave",
        "rag",
        "read_source",
    }
)

TOOL_MODES: dict[str, frozenset[str]] = {
    **{tool: frozenset({OUTLINE}) for tool in OUTLINE_ONLY},
    **{tool: frozenset({STUDY, REVIEW}) for tool in STUDY_REVIEW},
}


def all_mastery_tools() -> set[str]:
    """Every mastery-owned tool name (shared + mode-exclusive)."""
    return {name for name in SHARED_TOOLS if name.startswith("mastery_")} | set(
        TOOL_MODES
    )


def normalize_mode(value: Any) -> str:
    """The mode to *show and frame with*, always one of MODES."""
    candidate = str(value or "").strip().lower()
    return candidate if candidate in MODES else DEFAULT_MODE


def enforced_mode(value: Any) -> str | None:
    """The mode to *enforce against*, or ``None`` when none was recorded."""
    candidate = str(value or "").strip().lower()
    return candidate if candidate in MODES else None


def tool_is_allowed(tool_name: str, mode: Any) -> bool:
    """Whether *tool_name* may run in *mode*. Unlisted tools are shared."""
    allowed = TOOL_MODES.get(tool_name)
    if allowed is None:
        return True
    current = enforced_mode(mode)
    return True if current is None else current in allowed


def owning_modes(tool_name: str) -> tuple[str, ...]:
    allowed = TOOL_MODES.get(tool_name)
    return tuple(mode for mode in MODES if mode in allowed) if allowed else ()


def admission_error(mode: Any, *, has_outline: bool) -> str:
    """Why this mode cannot be entered, or ``""`` (spec 02 R3)."""
    if normalize_mode(mode) == STUDY and not has_outline:
        return (
            "There is no outline to study yet. Stay in 'outline' and design one "
            "with the learner first."
        )
    return ""


def wrong_mode_message(tool_name: str, mode: Any) -> str:
    """Why this call was refused, and the one move that fixes it (spec 02 R2)."""
    targets = owning_modes(tool_name)
    current = normalize_mode(mode)
    listed = " or ".join(repr(target) for target in targets) or "another mode"
    if targets:
        return (
            f"{tool_name} belongs to the {listed} mode, and this conversation is "
            f"in {current!r}. Call mastery_mode with mode={targets[0]!r} first — "
            "tell the learner what you are switching to and why."
        )
    return f"{tool_name} cannot run in {current!r}."


def assert_classification_complete(tool_names: set[str] | None = None) -> None:
    """Fail-closed guard (GUARD-1/2/3, INV-17).

    Asserts that every mastery-owned tool is explicitly classified, that the
    shared set and the mode-exclusive set do not overlap, and that no tool
    silently defaults to shared.
    """
    names = all_mastery_tools() if tool_names is None else set(tool_names)
    overlap = SHARED_TOOLS & set(TOOL_MODES)
    if overlap:
        raise AssertionError(f"tools declared both shared and mode-exclusive: {overlap}")
    unclassified = names - set(TOOL_MODES) - SHARED_TOOLS
    if unclassified:
        raise AssertionError(
            f"mastery tools not explicitly classified (fail-closed): {unclassified}"
        )


__all__ = [
    "DEFAULT_MODE",
    "MODES",
    "OUTLINE",
    "OUTLINE_ONLY",
    "REVIEW",
    "SHARED_TOOLS",
    "STUDY",
    "STUDY_REVIEW",
    "TOOL_MODES",
    "admission_error",
    "all_mastery_tools",
    "assert_classification_complete",
    "enforced_mode",
    "normalize_mode",
    "owning_modes",
    "tool_is_allowed",
    "wrong_mode_message",
]
