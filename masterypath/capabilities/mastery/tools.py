"""Mastery tools mounted on the loop — the seam to the engine (spec 06).

Every tool is mounted every turn; the mode is enforced when a tool is called
(ADR-005 / test). Only the outline tools are implemented at M2; the
quiz/grade/assess tools arrive with M3/M4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from masterypath.capabilities.mastery import mode
from masterypath.learning.outline import OutlineError
from masterypath.learning.service import LearningService
from masterypath.learning.storage import PreconditionError


@dataclass
class ToolContext:
    service: LearningService
    path_id: str
    session_mode: Any = None
    session_id: str = ""
    turn_id: str = ""


@dataclass
class ToolResult:
    ok: bool
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _wrong_mode_result(tool_name: str, ctx: ToolContext) -> ToolResult | None:
    # The RAW mode value: an unrecorded mode enforces nothing (INV-09).
    if mode.tool_is_allowed(tool_name, ctx.session_mode):
        return None
    return ToolResult(
        ok=False, content=mode.wrong_mode_message(tool_name, ctx.session_mode)
    )


class MasteryBuildTool:
    name = "mastery_build"
    description = (
        "Generate the outline. On an empty path this creates it; on a path that "
        "already has objectives it is a REBUILD and requires confirm=true."
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
            + (
                f" {len(result.gaps)} source gap(s) need the learner's decision."
                if result.gaps
                else ""
            )
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
                ctx.path_id,
                params.get("ops") or [],
                session_id=ctx.session_id,
                turn_id=ctx.turn_id,
            )
        except (OutlineError, PreconditionError) as exc:
            return ToolResult(ok=False, content=str(exc))
        payload = {
            "status": result.status,
            "applied": result.applied,
            "dropped_kp_ids": result.dropped_kp_ids,
            "gaps": [gap.model_dump() for gap in result.gaps],
        }
        return ToolResult(
            ok=True,
            content=f"Revised outline; applied {len(result.applied)} op(s).",
            metadata=payload,
        )


# Tools mounted on every mastery turn (M2 set).
TOOLS = {
    MasteryBuildTool.name: MasteryBuildTool(),
    MasteryReviseTool.name: MasteryReviseTool(),
}


__all__ = [
    "MasteryBuildTool",
    "MasteryReviseTool",
    "TOOLS",
    "ToolContext",
    "ToolResult",
]
