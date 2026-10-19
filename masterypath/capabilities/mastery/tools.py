"""Mastery tools mounted on the loop — the seam to the engine (spec 06).

Every tool is mounted every turn; the mode is enforced when a tool is called
(ADR-005). M2 added the outline tools; M3 adds quiz / grade / skip / note /
defer. The quiz tool ending the turn is signalled via ``end_turn`` on the
context; the loop honours it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import uuid

from masterypath.capabilities.mastery import mode
from masterypath.learning import policy
from masterypath.learning.models import (
    KnowledgeType,
    PendingOption,
    PendingQuestion,
)
from masterypath.learning.outline import OutlineError
from masterypath.learning.pending import parse_options
from masterypath.learning.question_card import QUESTION_CARD_KEY, attempt_number, build_question_card
from masterypath.learning.service import LearningService
from masterypath.learning.storage import PreconditionError

_QUESTION_TYPES = ("choice", "short", "open")
_DIFFICULTIES = ("easy", "medium", "hard")


@dataclass
class ToolContext:
    service: LearningService
    path_id: str
    session_mode: Any = None
    session_id: str = ""
    turn_id: str = ""
    end_turn: Callable[[], None] | None = None


@dataclass
class ToolResult:
    ok: bool
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _wrong_mode_result(tool_name: str, ctx: ToolContext) -> ToolResult | None:
    # The RAW mode value: an unrecorded mode enforces nothing (INV-09).
    if mode.tool_is_allowed(tool_name, ctx.session_mode):
        return None
    return ToolResult(ok=False, content=mode.wrong_mode_message(tool_name, ctx.session_mode))


def _canonical_labels(count: int) -> list[str]:
    return [chr(ord("A") + i) for i in range(count)]


def _read_options(raw: Any) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise OutlineError("options must be an array")
    if all(isinstance(item, dict) for item in raw):
        return [{"label": str(o.get("label", "")), "body": str(o.get("body", ""))} for o in raw]
    if all(isinstance(item, str) for item in raw):
        return [{"label": label, "body": body} for label, body in parse_options(raw).items()]
    raise OutlineError("options must be {label, body} objects or 'A: body' strings")


def _normalize_quiz(params: dict[str, Any]) -> tuple[str, list[dict[str, str]], str]:
    options = _read_options(params.get("options"))
    supplied = str(params.get("question_type") or "").strip().lower()
    if supplied and supplied not in _QUESTION_TYPES:
        raise OutlineError(f"question_type must be one of: {', '.join(_QUESTION_TYPES)}")
    q_type = supplied or ("choice" if options else "short")
    expected = str(params.get("expected_answer") or "").strip()
    if not expected:
        raise OutlineError("mastery_quiz needs expected_answer")

    if q_type != "choice":
        if options:
            raise OutlineError(f"options cannot be used with question_type={q_type!r}")
        return q_type, [], expected

    labels = [o["label"].upper() for o in options]
    if not options or set(labels) != set(_canonical_labels(len(options))):
        raise OutlineError("choice labels must run A, B, C… with one option each")
    bodies = [" ".join(o["body"].split()).casefold() for o in options]
    if not all(bodies) or len(set(bodies)) != len(bodies):
        raise OutlineError("choice option bodies must be unique and non-empty")
    choice_map = {o["label"].upper(): o["body"] for o in options}
    from masterypath.learning.grading import resolve_choice

    resolved = resolve_choice(expected, choice_map)
    if not resolved:
        raise OutlineError("choice expected_answer must resolve to one option label")
    normalized = [{"label": o["label"].upper(), "body": o["body"]} for o in options]
    return q_type, normalized, resolved


# -- outline tools --------------------------------------------------------
class MasteryBuildTool:
    name = "mastery_build"
    description = (
        "Generate the outline. Empty path creates; a path with objectives is a "
        "REBUILD and requires confirm=true."
    )

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        try:
            result = ctx.service.build(
                ctx.path_id,
                {"modules": params.get("modules")},
                confirm=bool(params.get("confirm")),
                session_id=ctx.session_id,
                turn_id=ctx.turn_id,
            )
        except (OutlineError, PreconditionError) as exc:
            return ToolResult(ok=False, content=str(exc))
        payload = {
            "status": result.status,
            "module_count": len(result.modules),
            "gaps": [gap.model_dump() for gap in result.gaps],
            "dropped": result.dropped,
        }
        content = result.message or (
            f"Built outline with {len(result.modules)} module(s)."
            + (f" {len(result.gaps)} source gap(s) need a decision." if result.gaps else "")
        )
        return ToolResult(ok=result.status == "built", content=content, metadata=payload)


class MasteryReviseTool:
    name = "mastery_revise"
    description = "Edit an existing outline with differential ops (progress-preserving)."

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        try:
            result = ctx.service.revise(
                ctx.path_id, params.get("ops") or [], session_id=ctx.session_id, turn_id=ctx.turn_id
            )
        except (OutlineError, PreconditionError) as exc:
            return ToolResult(ok=False, content=str(exc))
        return ToolResult(
            ok=True,
            content=f"Revised outline; applied {len(result.applied)} op(s).",
            metadata={
                "status": result.status,
                "applied": result.applied,
                "dropped_kp_ids": result.dropped_kp_ids,
                "gaps": [gap.model_dump() for gap in result.gaps],
            },
        )


# -- study tools ----------------------------------------------------------
class MasteryQuizTool:
    name = "mastery_quiz"
    description = (
        "Pose a question for a MEMORY or PROCEDURE objective. Registers the "
        "expected answer server-side and puts the question on the learner's card; "
        "this call ENDS THE TURN. Grade the answer on the next turn."
    )

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        progress = ctx.service.store.load(ctx.path_id)
        if progress is None:
            return ToolResult(ok=False, content="no mastery path is active")
        kp_id = str(params.get("knowledge_point_id") or "")
        kp, module_id, _ = policy.find_knowledge_point(progress, kp_id)
        if kp is None:
            return ToolResult(ok=False, content=f"unknown objective: {kp_id}")

        # Review re-tests what is already proven; it cannot examine a new one.
        if mode.enforced_mode(ctx.session_mode) == mode.REVIEW and not policy.is_mastered(
            progress, kp
        ):
            return ToolResult(
                ok=False,
                content=(
                    f"{kp.name!r} is not mastered yet; review re-tests proven "
                    "objectives. Switch to study to teach it."
                ),
            )

        question = str(params.get("question") or "").strip()
        if not question:
            return ToolResult(ok=False, content="mastery_quiz needs question")

        # Single slot: re-present the open card, ignore new params (INV-02).
        existing = ctx.service.store.get_open_interaction(ctx.path_id)
        if existing is not None:
            card = build_question_card(
                existing.question,
                objective_name=kp.name,
                attempt=attempt_number(progress, existing.question.knowledge_point_id),
            )
            if ctx.end_turn:
                ctx.end_turn()
            return ToolResult(
                ok=True,
                content="No new question: an open question already exists; re-presenting it.",
                metadata={"status": "already_pending", QUESTION_CARD_KEY: card},
            )

        try:
            q_type, options, expected = _normalize_quiz(params)
        except OutlineError as exc:
            return ToolResult(ok=False, content=str(exc))

        keywords = _open_keywords(params, q_type, expected)
        pending = PendingQuestion(
            question_id=uuid.uuid4().hex,
            knowledge_point_id=kp.id,
            module_id=module_id,
            prompt=question,
            question_type=q_type,
            expected_answer=expected,
            options=[PendingOption(**option) for option in options],
            explanation=str(params.get("explanation") or "").strip(),
            difficulty=str(params.get("difficulty") or "") if params.get("difficulty") in _DIFFICULTIES else "",
            accepted_answers=[str(a) for a in (params.get("accepted_answers") or [])],
            required_keywords=keywords[0],
            optional_keywords=keywords[1],
        )
        interaction = ctx.service.register_question(
            ctx.path_id, pending, session_id=ctx.session_id, turn_id=ctx.turn_id
        )
        if interaction is None:  # lost a race; re-present
            existing = ctx.service.store.get_open_interaction(ctx.path_id)
            assert existing is not None
            pending = existing.question
            interaction = existing
        card = build_question_card(
            pending if interaction is None else interaction.question,
            objective_name=kp.name,
            attempt=attempt_number(progress, kp.id),
        )
        notice = (
            "The question is on the learner's card and this turn ends here; grade "
            "their answer next turn with mastery_grade."
        )
        if kp.type in policy.QUALITATIVE_TYPES:
            notice += " This objective is gated qualitatively; grading will not open it."
        if ctx.end_turn:
            ctx.end_turn()
        return ToolResult(
            ok=True,
            content=notice,
            metadata={
                "status": "registered",
                "question_id": pending.question_id,
                QUESTION_CARD_KEY: card,
            },
        )


def _open_keywords(params: dict[str, Any], q_type: str, expected: str):
    if q_type != "open":
        return [], []
    required = [str(k) for k in (params.get("required_keywords") or [])]
    optional = [str(k) for k in (params.get("optional_keywords") or [])]
    if not required and not optional and expected:
        required = [expected]
    return required, optional


class MasteryGradeTool:
    name = "mastery_grade"
    description = "Grade the learner's answer to the open question (deterministic)."

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        question_id = str(params.get("question_id") or "")
        answer = str(params.get("answer") or "")
        hints = int(params.get("hints_used") or 0)
        try:
            result = ctx.service.grade(
                ctx.path_id,
                question_id,
                answer,
                hints_used=hints,
                review=mode.enforced_mode(ctx.session_mode) == mode.REVIEW,
                session_id=ctx.session_id,
                turn_id=ctx.turn_id,
            )
        except PreconditionError as exc:
            return ToolResult(ok=False, content=str(exc))
        status = result.get("status")
        if status == "ungraded":
            return ToolResult(
                ok=False,
                content=f"Not graded: {result.get('reason')}. Ask the learner to clarify.",
                metadata=result,
            )
        return ToolResult(
            ok=True,
            content=f"Graded: {result.get('result')}.",
            metadata=result,
        )


class MasterySkipQuestionTool:
    name = "mastery_skip_question"
    description = "Abandon the open question and clear it from the learner's card."

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        try:
            result = ctx.service.skip_question(
                ctx.path_id, str(params.get("question_id") or "")
            )
        except PreconditionError as exc:
            return ToolResult(ok=False, content=str(exc))
        return ToolResult(ok=True, content="Question skipped.", metadata=result)


class MasteryNoteExplainedTool:
    name = "mastery_note_explained"
    description = "Record what was taught. Does not assess or grant mastery."

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        summary = str(params.get("summary") or "").strip()
        if not summary:
            return ToolResult(ok=False, content="a teaching summary is required")
        try:
            result = ctx.service.note_explained(
                ctx.path_id, str(params.get("knowledge_point_id") or ""), summary
            )
        except PreconditionError as exc:
            return ToolResult(ok=False, content=str(exc))
        return ToolResult(ok=True, content="Recorded explanation (no mastery credit).", metadata=result)


class MasteryDeferObjectiveTool:
    name = "mastery_defer_objective"
    description = "Set a knowledge point aside for now without claiming mastery."

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        try:
            result = ctx.service.defer_objective(
                ctx.path_id,
                str(params.get("knowledge_point_id") or ""),
                note=str(params.get("note") or ""),
            )
        except PreconditionError as exc:
            return ToolResult(ok=False, content=str(exc))
        return ToolResult(ok=True, content="Objective deferred.", metadata=result)


class MasteryAssessTool:
    name = "mastery_assess"
    description = (
        "Judge a CONCEPT or DESIGN objective qualitatively from the learner's own "
        "explanation (Feynman-style). This is how those types are opened; a "
        "multiple-choice answer never opens them."
    )

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        progress = ctx.service.store.load(ctx.path_id)
        if progress is None:
            return ToolResult(ok=False, content="no mastery path is active")
        kp_id = str(params.get("knowledge_point_id") or "")
        kp, _, _ = policy.find_knowledge_point(progress, kp_id)
        if kp is None:
            return ToolResult(ok=False, content=f"unknown objective: {kp_id}")
        if mode.enforced_mode(ctx.session_mode) == mode.REVIEW and not policy.is_mastered(
            progress, kp
        ):
            return ToolResult(
                ok=False,
                content=f"{kp.name!r} is not mastered yet; review re-tests proven objectives.",
            )
        passed = bool(params.get("passed"))
        try:
            result = ctx.service.assess(
                ctx.path_id,
                kp_id,
                passed=passed,
                evidence=str(params.get("evidence") or ""),
                quality=params.get("quality"),
                review=mode.enforced_mode(ctx.session_mode) == mode.REVIEW,
                session_id=ctx.session_id,
                turn_id=ctx.turn_id,
            )
        except PreconditionError as exc:
            return ToolResult(ok=False, content=str(exc))
        return ToolResult(
            ok=True,
            content=f"Assessment recorded: {'passed' if passed else 'not yet'}.",
            metadata=result,
        )


class MasteryProposeObjectiveTool:
    name = "mastery_propose_objective"
    description = (
        "Record a candidate objective discovered while learning — a missing "
        "prerequisite, a new sub-topic. It does NOT change the map or the "
        "frontier; the outline reconciles it later."
    )

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        name = str(params.get("name") or "").strip()
        if len(name) < 2:
            return ToolResult(ok=False, content="a candidate objective needs a name of 2+ characters")
        try:
            result = ctx.service.propose_objective(
                ctx.path_id,
                name=name,
                kp_type=str(params.get("type") or ""),
                reason=str(params.get("reason") or ""),
                module_id=str(params.get("module_id") or ""),
                source_ids=[str(s) for s in (params.get("sources") or [])],
                session_id=ctx.session_id,
                turn_id=ctx.turn_id,
            )
        except (ValueError, PreconditionError) as exc:
            return ToolResult(ok=False, content=str(exc))
        return ToolResult(ok=True, content="Recorded a candidate objective.", metadata=result)


class MasteryNoteGapTool:
    name = "mastery_note_gap"
    description = (
        "Record a coverage gap found while learning (a goal requirement the "
        "materials do not cover, or a selected source nothing uses). Does not "
        "change the map."
    )

    def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        refusal = _wrong_mode_result(self.name, ctx)
        if refusal is not None:
            return refusal
        kind = str(params.get("kind") or "").strip()
        if kind not in ("goal_gap", "source_omission"):
            return ToolResult(ok=False, content="kind must be goal_gap or source_omission")
        try:
            result = ctx.service.note_gap(
                ctx.path_id,
                kind=kind,
                ref=str(params.get("ref") or ""),
                reason=str(params.get("reason") or ""),
            )
        except (ValueError, PreconditionError) as exc:
            return ToolResult(ok=False, content=str(exc))
        return ToolResult(ok=True, content="Recorded a coverage gap.", metadata=result)


# JSON Schema for every mastery tool. Hand-written on purpose: the executors use
# ``params.get(...)`` so their signatures are not a reliable source, and an
# explicit schema is directly assertable in tests. ``strict`` is deliberately
# omitted — not every OpenAI-compatible provider supports it.
TOOL_PARAMETERS: dict[str, dict[str, Any]] = {
    "mastery_build": {
        "type": "object",
        "properties": {
            "modules": {
                "type": "array",
                "description": "Outline modules with knowledge_points.",
                "items": {"type": "object"},
            },
            "confirm": {
                "type": "boolean",
                "description": "Required to rebuild a non-empty outline.",
            },
        },
        "required": [],
    },
    "mastery_revise": {
        "type": "object",
        "properties": {
            "ops": {
                "type": "array",
                "description": "Differential outline operations.",
                "items": {"type": "object"},
            }
        },
        "required": ["ops"],
    },
    "mastery_quiz": {
        "type": "object",
        "properties": {
            "knowledge_point_id": {"type": "string"},
            "question": {"type": "string"},
            "expected_answer": {"type": "string"},
            "question_type": {
                "type": "string",
                "enum": list(_QUESTION_TYPES),
            },
            "options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["label", "body"],
                },
            },
            "explanation": {"type": "string"},
            "difficulty": {"type": "string", "enum": list(_DIFFICULTIES)},
            "accepted_answers": {"type": "array", "items": {"type": "string"}},
            "required_keywords": {"type": "array", "items": {"type": "string"}},
            "optional_keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["knowledge_point_id", "question", "expected_answer"],
    },
    "mastery_grade": {
        "type": "object",
        "properties": {
            "question_id": {"type": "string"},
            "answer": {"type": "string"},
            "hints_used": {"type": "integer", "minimum": 0},
        },
        "required": ["question_id", "answer"],
    },
    "mastery_skip_question": {
        "type": "object",
        "properties": {"question_id": {"type": "string"}},
        "required": ["question_id"],
    },
    "mastery_note_explained": {
        "type": "object",
        "properties": {
            "knowledge_point_id": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["knowledge_point_id", "summary"],
    },
    "mastery_defer_objective": {
        "type": "object",
        "properties": {
            "knowledge_point_id": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["knowledge_point_id"],
    },
    "mastery_assess": {
        "type": "object",
        "properties": {
            "knowledge_point_id": {"type": "string"},
            "passed": {"type": "boolean"},
            "evidence": {"type": "string"},
            "quality": {"type": "number"},
        },
        "required": ["knowledge_point_id", "passed"],
    },
    "mastery_propose_objective": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {
                "type": "string",
                "enum": [item.value for item in KnowledgeType],
            },
            "reason": {"type": "string"},
            "module_id": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name"],
    },
    "mastery_note_gap": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["goal_gap", "source_omission"]},
            "ref": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["kind"],
    },
}


def tool_definitions(tools: dict[str, Any]) -> list[dict[str, Any]]:
    """OpenAI tool definitions for the mounted mastery tools."""
    definitions: list[dict[str, Any]] = []
    for name in sorted(tools):
        tool = tools[name]
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": getattr(tool, "description", "") or name,
                    "parameters": TOOL_PARAMETERS.get(
                        name, {"type": "object", "properties": {}}
                    ),
                },
            }
        )
    return definitions


# Tools mounted on every mastery turn (M2 + M3 + M4 + capture set).
TOOLS = {
    MasteryBuildTool.name: MasteryBuildTool(),
    MasteryReviseTool.name: MasteryReviseTool(),
    MasteryQuizTool.name: MasteryQuizTool(),
    MasteryGradeTool.name: MasteryGradeTool(),
    MasteryAssessTool.name: MasteryAssessTool(),
    MasterySkipQuestionTool.name: MasterySkipQuestionTool(),
    MasteryNoteExplainedTool.name: MasteryNoteExplainedTool(),
    MasteryDeferObjectiveTool.name: MasteryDeferObjectiveTool(),
    MasteryProposeObjectiveTool.name: MasteryProposeObjectiveTool(),
    MasteryNoteGapTool.name: MasteryNoteGapTool(),
}


__all__ = [
    "TOOLS",
    "TOOL_PARAMETERS",
    "MasteryAssessTool",
    "MasteryBuildTool",
    "MasteryDeferObjectiveTool",
    "MasteryGradeTool",
    "MasteryNoteExplainedTool",
    "MasteryNoteGapTool",
    "MasteryProposeObjectiveTool",
    "MasteryQuizTool",
    "MasteryReviseTool",
    "MasterySkipQuestionTool",
    "ToolContext",
    "ToolResult",
    "tool_definitions",
]
