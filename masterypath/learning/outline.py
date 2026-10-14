"""Outline building & revision — pure transforms (spec 06 §二/§三, ADR-004/011).

No I/O, no LLM. Given a :class:`LearningProgress` and a payload, these
functions mutate the aggregate and return a result, detecting source gaps
(INV-23) and enforcing build/revise validation (INV-40/41/42).

Ids are assigned server-side; ``build`` references prerequisites by *name*
(the model has no ids yet), ``revise`` references everything by id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from masterypath.learning.models import (
    GapKind,
    GapResolution,
    KnowledgePoint,
    KnowledgeType,
    LearningModule,
    LearningProgress,
    SourceGap,
)

_BASELINE_KEYS = (
    "mastery_levels",
    "qualitative_mastery",
    "quiz_attempts",
    "learning_evidence",
    "repetition_states",
    "review_queue",
    "learner_mastery_overrides",
    "deferred_objectives",
    "explained_objectives",
    "knowledge_types",
)


class OutlineError(ValueError):
    """Invalid build/revise payload (INV-40)."""


@dataclass
class BuildResult:
    status: str  # "built" | "refused_rebuild"
    modules: list[LearningModule] = field(default_factory=list)
    gaps: list[SourceGap] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    rebuilt: bool = False
    message: str = ""


@dataclass
class ReviseResult:
    status: str = "revised"
    applied: list[str] = field(default_factory=list)
    dropped_kp_ids: list[str] = field(default_factory=list)
    gaps: list[SourceGap] = field(default_factory=list)
    message: str = ""


# -- helpers --------------------------------------------------------------
def _resolve_source(label: str, source_map: dict[str, str] | None) -> str:
    if source_map is None:
        return label
    return source_map.get(label, "")


def _next_id(prefix: str, existing: set[str]) -> str:
    index = 1
    while f"{prefix}{index}" in existing:
        index += 1
    return f"{prefix}{index}"


def _existing_ids(progress: LearningProgress) -> set[str]:
    ids: set[str] = set()
    for module in progress.modules:
        ids.add(module.id)
        for kp in module.knowledge_points:
            ids.add(kp.id)
    return ids


def _reset_learning_state(progress: LearningProgress) -> None:
    for key in _BASELINE_KEYS:
        setattr(progress, key, {} if isinstance(getattr(progress, key), dict) else [])
    progress.source_gaps = []
    progress.pending_question = None
    progress.current_module_id = ""
    progress.current_kp_index = 0


def _detect_gaps(
    modules: list[LearningModule],
    selected_source_ids: set[str],
    existing_gap_count: int,
) -> list[SourceGap]:
    gaps: list[SourceGap] = []
    counter = existing_gap_count

    used: set[str] = set()
    for module in modules:
        for kp in module.knowledge_points:
            used.update(kp.source_ids)
            if not kp.source_ids:
                counter += 1
                gaps.append(
                    SourceGap(
                        id=f"g{counter}",
                        kind=GapKind.GOAL_GAP,
                        ref=kp.id,
                        reason=f"objective {kp.name!r} has no supporting source",
                    )
                )
    for source_id in sorted(selected_source_ids - used):
        counter += 1
        gaps.append(
            SourceGap(
                id=f"g{counter}",
                kind=GapKind.SOURCE_OMISSION,
                ref=source_id,
                reason=f"selected source {source_id!r} is not used by any module",
            )
        )
    return gaps


# -- build ----------------------------------------------------------------
def build_outline(
    progress: LearningProgress,
    payload: dict[str, Any],
    *,
    confirm: bool = False,
    source_map: dict[str, str] | None = None,
    selected_source_ids: set[str] | None = None,
) -> BuildResult:
    """Create or (with *confirm*) replace the outline (ADR-004 / INV-41)."""
    modules = _parse_build_payload(payload, source_map)
    has_content = any(m.knowledge_points for m in progress.modules)
    selected = set(selected_source_ids or [])

    if has_content and not confirm:
        dropped = [kp.id for module in progress.modules for kp in module.knowledge_points]
        return BuildResult(
            status="refused_rebuild",
            dropped=dropped,
            message=(
                "This path already has an outline. Rebuilding resets all progress; "
                "pass confirm=true after telling the learner what will be lost."
            ),
        )

    replacing = has_content
    if replacing:
        _reset_learning_state(progress)
    progress.modules = modules
    for module in modules:
        for kp in module.knowledge_points:
            progress.knowledge_types[kp.id] = kp.type
    if modules:
        progress.current_module_id = modules[0].id

    gaps = _detect_gaps(modules, selected, len(progress.source_gaps))
    progress.source_gaps = gaps
    return BuildResult(status="built", modules=modules, gaps=gaps, rebuilt=replacing)


def _parse_build_payload(
    payload: dict[str, Any], source_map: dict[str, str] | None
) -> list[LearningModule]:
    raw_modules = payload.get("modules")
    if not isinstance(raw_modules, list) or not raw_modules:
        raise OutlineError(
            "mastery_build needs a non-empty 'modules' array: "
            '\'modules\': [{"name": "...", "knowledge_points": '
            '[{"name": "...", "type": "memory|procedure|concept|design"}]}]'
        )
    names: set[str] = set()
    parsed: list[tuple[str, dict, list[tuple[str, str, KnowledgeType, dict]]]] = []
    m_counter = k_counter = 0
    for raw_module in raw_modules:
        if not isinstance(raw_module, dict):
            raise OutlineError("each module must be an object")
        m_counter += 1
        module_id = f"m{m_counter}"
        kp_specs = raw_module.get("knowledge_points") or []
        if not isinstance(kp_specs, list):
            raise OutlineError("module.knowledge_points must be an array")
        kps: list[tuple[str, str, KnowledgeType, dict]] = []
        for spec in kp_specs:
            if not isinstance(spec, dict):
                raise OutlineError("each knowledge point must be an object")
            name = str(spec.get("name") or "").strip()
            if len(name) < 2:
                raise OutlineError(
                    f"knowledge point name must be at least 2 characters: {name!r}"
                )
            if name in names:
                raise OutlineError(f"duplicate knowledge point name: {name!r}")
            names.add(name)
            try:
                kp_type = KnowledgeType(spec.get("type"))
            except ValueError as exc:
                raise OutlineError(
                    f"knowledge point {name!r} has invalid type {spec.get('type')!r}"
                ) from exc
            k_counter += 1
            kps.append((f"k{k_counter}", name, kp_type, spec))
        parsed.append((module_id, raw_module, kps))

    name_to_id = {name: kid for _, _, kps in parsed for kid, name, _, _ in kps}

    modules: list[LearningModule] = []
    for order, (module_id, raw_module, kps) in enumerate(parsed):
        knowledge_points: list[KnowledgePoint] = []
        for kid, name, kp_type, spec in kps:
            prereq_names = spec.get("prerequisites") or []
            prereq_ids: list[str] = []
            for prereq in prereq_names:
                resolved = name_to_id.get(str(prereq).strip())
                if resolved is None:
                    raise OutlineError(
                        f"knowledge point {name!r} references unknown prerequisite "
                        f"{prereq!r}"
                    )
                prereq_ids.append(resolved)
            raw_sources = spec.get("sources") or []
            source_ids = [
                resolved
                for resolved in (_resolve_source(str(s), source_map) for s in raw_sources)
                if resolved
            ]
            knowledge_points.append(
                KnowledgePoint(
                    id=kid,
                    name=name,
                    type=kp_type,
                    module_id=module_id,
                    prerequisite_ids=prereq_ids,
                    source_ids=source_ids,
                )
            )
        raw_materials = raw_module.get("materials") or []
        module_sources = [
            resolved
            for resolved in (_resolve_source(str(m), source_map) for m in raw_materials)
            if resolved
        ]
        # materials ground the module; attach to KPs that declare no source.
        for kp in knowledge_points:
            if not kp.source_ids and module_sources:
                kp.source_ids = list(module_sources)
        modules.append(
            LearningModule(
                id=module_id,
                name=str(raw_module.get("name") or module_id),
                order=order,
                objective=str(raw_module.get("objective") or ""),
                knowledge_points=knowledge_points,
            )
        )
    return modules


# -- revise ---------------------------------------------------------------
def revise_outline(
    progress: LearningProgress,
    ops: list[dict[str, Any]],
    *,
    selected_source_ids: set[str] | None = None,
) -> ReviseResult:
    """Apply differential ops, preserving progress for untouched objectives."""
    if not isinstance(ops, list):
        raise OutlineError("mastery_revise needs an 'ops' array")
    result = ReviseResult()
    for op in ops:
        if not isinstance(op, dict):
            raise OutlineError("each op must be an object")
        name = str(op.get("op") or "")
        handler = _OPS.get(name)
        if handler is None:
            raise OutlineError(f"unknown revise op: {name!r}")
        handler(progress, op, result)
    result.gaps = _detect_gaps(
        progress.modules, set(selected_source_ids or []), 0
    )
    progress.source_gaps = result.gaps
    return result


def _find_module(progress: LearningProgress, module_id: str) -> LearningModule:
    for module in progress.modules:
        if module.id == module_id:
            return module
    raise OutlineError(f"unknown module_id: {module_id!r}")


def _find_kp(progress: LearningProgress, kp_id: str) -> tuple[KnowledgePoint, LearningModule]:
    for module in progress.modules:
        for kp in module.knowledge_points:
            if kp.id == kp_id:
                return kp, module
    raise OutlineError(f"unknown knowledge_point_id: {kp_id!r}")


def _drop_kp_state(progress: LearningProgress, kp_id: str) -> None:
    progress.mastery_levels.pop(kp_id, None)
    progress.qualitative_mastery.pop(kp_id, None)
    progress.knowledge_types.pop(kp_id, None)
    progress.repetition_states.pop(kp_id, None)
    progress.learner_mastery_overrides.pop(kp_id, None)
    progress.deferred_objectives.pop(kp_id, None)
    progress.explained_objectives.pop(kp_id, None)
    progress.quiz_attempts = [
        a for a in progress.quiz_attempts if a.knowledge_point_id != kp_id
    ]
    progress.learning_evidence = [
        e for e in progress.learning_evidence if e.knowledge_point_id != kp_id
    ]
    progress.review_queue = [
        t for t in progress.review_queue if t.knowledge_point_id != kp_id
    ]


def _op_add_module(progress, op, result):
    module_id = _next_id("m", _existing_ids(progress))
    progress.modules.append(
        LearningModule(
            id=module_id,
            name=str(op.get("name") or module_id),
            order=len(progress.modules),
            objective=str(op.get("objective") or ""),
        )
    )
    result.applied.append(f"add_module:{module_id}")


def _op_update_module(progress, op, result):
    module = _find_module(progress, str(op.get("module_id")))
    if op.get("name") is not None:
        module.name = str(op["name"])
    if op.get("objective") is not None:
        module.objective = str(op["objective"])
    result.applied.append(f"update_module:{module.id}")


def _op_remove_module(progress, op, result):
    module = _find_module(progress, str(op.get("module_id")))
    for kp in module.knowledge_points:
        _drop_kp_state(progress, kp.id)
        result.dropped_kp_ids.append(kp.id)
    progress.modules = [m for m in progress.modules if m.id != module.id]
    result.applied.append(f"remove_module:{module.id}")


def _op_add_kp(progress, op, result):
    module = _find_module(progress, str(op.get("module_id")))
    name = str(op.get("name") or "").strip()
    if len(name) < 2:
        raise OutlineError("new knowledge point name must be at least 2 characters")
    try:
        kp_type = KnowledgeType(op.get("type"))
    except ValueError as exc:
        raise OutlineError(f"invalid type for new kp {name!r}") from exc
    kp_id = _next_id("k", _existing_ids(progress))
    prereqs = [str(p) for p in (op.get("prerequisites") or [])]
    module.knowledge_points.append(
        KnowledgePoint(
            id=kp_id,
            name=name,
            type=kp_type,
            module_id=module.id,
            prerequisite_ids=prereqs,
        )
    )
    progress.knowledge_types[kp_id] = kp_type
    result.applied.append(f"add_kp:{kp_id}")


def _op_update_kp(progress, op, result):
    kp, _ = _find_kp(progress, str(op.get("kp_id")))
    if op.get("type") is not None and KnowledgeType(op["type"]) is not kp.type:
        raise OutlineError(
            "knowledge point type is read-only (ADR-003); remove and re-add to change it"
        )
    if op.get("name") is not None:
        kp.name = str(op["name"])
    if op.get("prerequisites") is not None:
        kp.prerequisite_ids = [str(p) for p in op["prerequisites"]]
    result.applied.append(f"update_kp:{kp.id}")


def _op_remove_kp(progress, op, result):
    kp, module = _find_kp(progress, str(op.get("kp_id")))
    _drop_kp_state(progress, kp.id)
    module.knowledge_points = [k for k in module.knowledge_points if k.id != kp.id]
    result.dropped_kp_ids.append(kp.id)
    result.applied.append(f"remove_kp:{kp.id}")


def _op_move_kp(progress, op, result):
    kp, source_module = _find_kp(progress, str(op.get("kp_id")))
    target = _find_module(progress, str(op.get("module_id")))
    source_module.knowledge_points = [
        k for k in source_module.knowledge_points if k.id != kp.id
    ]
    kp.module_id = target.id
    target.knowledge_points.append(kp)
    result.applied.append(f"move_kp:{kp.id}")


def _op_reorder(progress, op, result):
    module = _find_module(progress, str(op.get("module_id")))
    order = {str(kid): i for i, kid in enumerate(op.get("kp_ids") or [])}
    if set(order) != {kp.id for kp in module.knowledge_points}:
        raise OutlineError("reorder must list every knowledge point id exactly once")
    module.knowledge_points.sort(key=lambda kp: order[kp.id])
    result.applied.append(f"reorder:{module.id}")


_OPS = {
    "add_module": _op_add_module,
    "update_module": _op_update_module,
    "remove_module": _op_remove_module,
    "add_kp": _op_add_kp,
    "update_kp": _op_update_kp,
    "remove_kp": _op_remove_kp,
    "move_kp": _op_move_kp,
    "reorder": _op_reorder,
}


# -- gap resolution -------------------------------------------------------
def resolve_gap(
    progress: LearningProgress, gap_id: str, action: str
) -> SourceGap:
    """Accept a gap (mark ungrounded) or record a regeneration attempt."""
    for gap in progress.source_gaps:
        if gap.id == gap_id:
            if action == "accept":
                gap.resolution = GapResolution.ACCEPTED
            elif action == "regenerate":
                gap.resolution = GapResolution.REGENERATED
            else:
                raise OutlineError(f"unknown gap action: {action!r}")
            return gap
    raise OutlineError(f"unknown gap_id: {gap_id!r}")


__all__ = [
    "BuildResult",
    "OutlineError",
    "ReviseResult",
    "build_outline",
    "resolve_gap",
    "revise_outline",
]
