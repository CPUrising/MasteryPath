"""Learning service — the seam between callers (tools / REST) and the store.

Wraps pure outline transforms in ``store.mutate`` so state + events commit
together (INV-51). Knows nothing about LLMs (ADR-014).
"""

from __future__ import annotations

from typing import Any
import time
import uuid

from masterypath.learning import grading, mastery, policy, scheduler
from masterypath.learning.models import (
    AssessmentResult,
    AssessmentType,
    DeferredObjective,
    InteractionStatus,
    LearningEvidence,
    KnowledgeType,
    LearnerMasteryOverride,
    LearningProgress,
    MasteryInteraction,
    QuizAttempt,
    QuestionBankEntry,
)
from masterypath.learning.outline import (
    BuildResult,
    ReviseResult,
    build_outline,
    resolve_gap,
    revise_outline,
)
from masterypath.learning.storage import LearningStore, PreconditionError


class LearningService:
    def __init__(
        self,
        store: LearningStore,
        *,
        source_map: dict[str, str] | None = None,
        selected_source_ids: set[str] | None = None,
    ) -> None:
        self.store = store
        self.source_map = source_map
        self.selected_source_ids = selected_source_ids

    # -- lifecycle ---------------------------------------------------------
    def create_path(
        self, path_id: str, *, goal: str = "", name: str = ""
    ) -> LearningProgress:
        progress = LearningProgress(path_id=path_id, goal=goal, name=name)
        return self.store.create(progress)

    def get_state(self, path_id: str) -> dict[str, Any]:
        progress = self.store.load(path_id)
        if progress is None:
            return {"status": "missing", "path_id": path_id}
        step = policy.next_objective(progress)
        return {
            "status": "active",
            "path_id": path_id,
            "name": progress.name,
            "goal": progress.goal,
            "version": progress.version,
            "map": policy.map_summary(progress),
            "next": step.to_dict(),
            "gaps": [gap.model_dump() for gap in progress.source_gaps],
            "pending_question": progress.pending_question
            and _public(progress.pending_question),
            "due_reviews": [task.model_dump() for task in policy.due_reviews(progress)],
        }

    # -- outline -----------------------------------------------------------
    def build(
        self,
        path_id: str,
        payload: dict[str, Any],
        *,
        confirm: bool = False,
        session_id: str = "",
        turn_id: str = "",
    ) -> BuildResult:
        def fn(tx):
            result = build_outline(
                tx.progress,
                payload,
                confirm=confirm,
                source_map=self.source_map,
                selected_source_ids=self.selected_source_ids,
            )
            if result.status == "built":
                event_type = "path.rebuilt" if result.rebuilt else "outline.built"
                tx.emit(
                    event_type,
                    {
                        "module_count": len(result.modules),
                        "gap_ids": [gap.id for gap in result.gaps],
                    },
                )
            return result

        return self.store.mutate(path_id, fn, create_if_missing=True)

    def revise(
        self,
        path_id: str,
        ops: list[dict[str, Any]],
        *,
        session_id: str = "",
        turn_id: str = "",
    ) -> ReviseResult:
        def fn(tx):
            result = revise_outline(
                tx.progress, ops, selected_source_ids=self.selected_source_ids
            )
            tx.emit(
                "outline.revised",
                {
                    "applied": result.applied,
                    "dropped_kp_ids": result.dropped_kp_ids,
                },
            )
            return result

        return self.store.mutate(path_id, fn)

    def resolve_gap(self, path_id: str, gap_id: str, action: str):
        def fn(tx):
            gap = resolve_gap(tx.progress, gap_id, action)
            tx.emit("gap.resolved", {"gap_id": gap_id, "action": action})
            return gap

        return self.store.mutate(path_id, fn)

    def override_mastery(self, path_id: str, kp_id: str, note: str = ""):
        """Learner declares mastery: advances frontier, writes no score (INV-01)."""

        def fn(tx):
            kp, _ = tx.progress.find_knowledge_point(kp_id)
            tx.require(kp is not None, f"unknown knowledge point: {kp_id}")
            assert kp is not None
            was_mastered = policy.is_mastered(tx.progress, kp)
            tx.progress.learner_mastery_overrides[kp_id] = LearnerMasteryOverride(
                knowledge_point_id=kp_id, note=note
            )
            gate_cleared = policy.is_mastered(tx.progress, kp) and not was_mastered
            if gate_cleared:
                _schedule_after(
                    tx, kp, result="correct", hints_used=0, review=False,
                    gate_cleared=True, source="learner",
                )
            tx.emit("mastery.override", {"knowledge_point_id": kp_id, "note": note})
            return {"knowledge_point_id": kp_id, "source": "learner", "gate_cleared": gate_cleared}

        return self.store.mutate(path_id, fn)

    # -- questions / grading (M3) -----------------------------------------
    def register_question(
        self,
        path_id: str,
        pending,
        *,
        session_id: str = "",
        turn_id: str = "",
    ):
        """Register a posed question. Returns the interaction, or ``None`` when
        one is already open (single slot, INV-02)."""
        if self.store.get_open_interaction(path_id) is not None:
            return None

        def fn(tx):
            if tx.get_open_interaction() is not None:
                return None
            tx.progress.pending_question = pending
            interaction = MasteryInteraction(
                interaction_id=pending.question_id,
                path_id=path_id,
                question=pending,
                status=InteractionStatus.AWAITING_INPUT,
                session_id=session_id,
                turn_id=turn_id,
            )
            tx.save_interaction(interaction)
            tx.emit(
                "question.registered",
                {
                    "question_id": pending.question_id,
                    "knowledge_point_id": pending.knowledge_point_id,
                    "question_type": pending.question_type,
                },
            )
            return interaction

        return self.store.mutate(path_id, fn)

    def grade(
        self,
        path_id: str,
        question_id: str,
        answer: str,
        *,
        hints_used: int = 0,
        review: bool = False,
        session_id: str = "",
        turn_id: str = "",
    ) -> dict[str, Any]:
        interaction = self.store.get_interaction(path_id, question_id)
        if interaction is None:
            raise PreconditionError(f"unknown question_id: {question_id}")
        if interaction.status == InteractionStatus.GRADED:
            return {**interaction.result, "status": "already_graded"}
        if not interaction.is_open:
            raise PreconditionError("interaction is not gradable")

        decision = grading.grade(interaction.question, answer)
        if decision.result == "ungraded":
            # Zero state change (INV-46): never record a guess as an answer.
            return {"status": "ungraded", "reason": decision.reason}

        def fn(tx):
            current = tx.get_interaction(question_id)
            tx.require(current is not None, "unknown question_id")
            if current.status == InteractionStatus.GRADED:
                return {**current.result, "status": "already_graded"}
            pending = current.question
            kp, _ = tx.progress.find_knowledge_point(pending.knowledge_point_id)
            tx.require(kp is not None, f"unknown objective: {pending.knowledge_point_id}")
            assert kp is not None

            result = decision.result
            if pending.question_type == "open" and result == "correct":
                result = "partial"  # open never grants mastery alone (INV-35)
            if hints_used > 0 and result == "correct":
                result = "partial"  # INV-36
            is_correct = result == "correct"

            was_mastered = policy.is_mastered(tx.progress, kp)
            before = float(tx.progress.mastery_levels.get(kp.id, 0.0))
            evidence_id = uuid.uuid4().hex
            tx.progress.quiz_attempts.append(
                QuizAttempt(
                    question_id=pending.question_id,
                    knowledge_point_id=kp.id,
                    module_id=pending.module_id,
                    is_correct=is_correct,
                    user_answer=answer,
                    independent=hints_used == 0,
                )
            )
            tx.progress.learning_evidence.append(
                LearningEvidence(
                    evidence_id=evidence_id,
                    question_id=pending.question_id,
                    knowledge_point_id=kp.id,
                    assessment_type=AssessmentType.REVIEW if review else AssessmentType.QUIZ,
                    result=AssessmentResult(result),
                    hints_used=hints_used,
                    session_id=session_id,
                    turn_id=turn_id,
                    source="mastery_path",
                )
            )
            if kp.type not in policy.QUALITATIVE_TYPES:
                tx.progress.mastery_levels[kp.id] = mastery.compute_mastery(
                    policy.active_attempts(tx.progress, kp.id)
                )
            after = float(tx.progress.mastery_levels.get(kp.id, 0.0))
            gate_cleared = policy.is_mastered(tx.progress, kp) and not was_mastered
            source = policy.mastery_source(tx.progress, kp)
            _schedule_after(
                tx, kp, result=result, hints_used=hints_used, review=review,
                gate_cleared=gate_cleared, source=source, evidence_id=evidence_id,
            )
            tx.progress.pending_question = None

            payload = {
                "status": "graded",
                "knowledge_point_id": kp.id,
                "is_correct": is_correct,
                "result": result,
                "mastery_before": before,
                "mastery_after": after,
                "gate_cleared": gate_cleared,
                "source": source,
                "explanation": pending.explanation,
            }
            current.status = InteractionStatus.GRADED
            current.user_answer = answer
            current.result = payload
            tx.save_interaction(current)
            tx.save_bank_entry(
                QuestionBankEntry(
                    entry_id=uuid.uuid4().hex,
                    path_id=path_id,
                    knowledge_point_id=kp.id,
                    knowledge_point_name=kp.name,
                    question_id=pending.question_id,
                    question=pending.prompt,
                    question_type=pending.question_type,
                    options=[option.model_dump() for option in pending.options],
                    correct_answer=pending.expected_answer,
                    explanation=pending.explanation,
                    difficulty=pending.difficulty,
                    user_answer=answer,
                    is_correct=is_correct,
                    result=result,
                    source="mastery_path",
                )
            )
            tx.emit(
                "attempt.graded",
                {
                    "question_id": pending.question_id,
                    "knowledge_point_id": kp.id,
                    "is_correct": is_correct,
                    "result": result,
                    "hints_used": hints_used,
                    "mastery_after": after,
                },
            )
            if gate_cleared:
                tx.emit(
                    "objective.mastered",
                    {"knowledge_point_id": kp.id, "source": payload["source"]},
                )
            return payload

        return self.store.mutate(path_id, fn)

    def assess(
        self,
        path_id: str,
        kp_id: str,
        *,
        passed: bool,
        evidence: str = "",
        quality: float | None = None,
        review: bool = False,
        session_id: str = "",
        turn_id: str = "",
    ) -> dict[str, Any]:
        """Feynman-style qualitative gate for CONCEPT / DESIGN (ADR-007 / INV-05).

        Refuses quantitative objectives: those are opened by ``grade``.
        """

        def fn(tx):
            kp, _ = tx.progress.find_knowledge_point(kp_id)
            tx.require(kp is not None, f"unknown objective: {kp_id}")
            assert kp is not None
            tx.require(
                kp.type in policy.QUALITATIVE_TYPES,
                "mastery_assess is for concept/design objectives; use mastery_grade "
                "for memory/procedure",
            )
            was_mastered = policy.is_mastered(tx.progress, kp)
            tx.progress.qualitative_mastery[kp_id] = bool(passed)
            evidence_id = uuid.uuid4().hex
            tx.progress.learning_evidence.append(
                LearningEvidence(
                    evidence_id=evidence_id,
                    knowledge_point_id=kp_id,
                    assessment_type=AssessmentType.QUALITATIVE,
                    result=AssessmentResult.CORRECT if passed else AssessmentResult.PARTIAL,
                    quality=1.0 if passed else (0.2 if quality is None else quality),
                    hints_used=0,
                    session_id=session_id,
                    turn_id=turn_id,
                    source="mastery_path",
                )
            )
            gate_cleared = policy.is_mastered(tx.progress, kp) and not was_mastered
            source = policy.mastery_source(tx.progress, kp)
            _schedule_after(
                tx, kp, result="correct" if passed else "incorrect", hints_used=0,
                review=review, gate_cleared=gate_cleared, source=source,
                evidence_id=evidence_id,
            )
            if tx.progress.pending_question and (
                tx.progress.pending_question.knowledge_point_id == kp_id
            ):
                tx.progress.pending_question = None
            payload = {
                "status": "assessed",
                "knowledge_point_id": kp_id,
                "passed": bool(passed),
                "gate_cleared": gate_cleared,
                "source": source,
            }
            tx.emit(
                "qualitative.assessed",
                {"knowledge_point_id": kp_id, "passed": bool(passed), "quality": quality},
            )
            if gate_cleared:
                tx.emit(
                    "objective.mastered",
                    {"knowledge_point_id": kp_id, "source": source},
                )
            tx.save_bank_entry(
                QuestionBankEntry(
                    entry_id=uuid.uuid4().hex,
                    path_id=path_id,
                    knowledge_point_id=kp_id,
                    knowledge_point_name=kp.name,
                    question=kp.name,
                    question_type="written",
                    user_answer=evidence,
                    is_correct=bool(passed),
                    result="correct" if passed else "partial",
                    source="mastery_path",
                )
            )
            return payload

        return self.store.mutate(path_id, fn)

    def skip_question(self, path_id: str, question_id: str, *, session_id: str = "", turn_id: str = ""):
        def fn(tx):
            current = tx.get_interaction(question_id)
            tx.require(current is not None, "unknown question_id")
            if current.is_terminal:
                return {"status": current.status.value}
            current.status = InteractionStatus.ABANDONED
            tx.save_interaction(current)
            tx.progress.pending_question = None
            tx.emit("question.skipped", {"question_id": question_id})
            return {"status": "abandoned", "question_id": question_id}

        return self.store.mutate(path_id, fn)

    def note_explained(self, path_id: str, kp_id: str, summary: str):
        def fn(tx):
            kp, _ = tx.progress.find_knowledge_point(kp_id)
            tx.require(kp is not None, f"unknown objective: {kp_id}")
            tx.progress.explained_objectives[kp_id] = {"summary": summary}
            tx.emit("objective.explained", {"knowledge_point_id": kp_id, "summary": summary})
            return {"knowledge_point_id": kp_id, "mastery_credit": False}

        return self.store.mutate(path_id, fn)

    def defer_objective(self, path_id: str, kp_id: str, note: str = ""):
        def fn(tx):
            kp, _ = tx.progress.find_knowledge_point(kp_id)
            tx.require(kp is not None, f"unknown objective: {kp_id}")
            tx.progress.deferred_objectives[kp_id] = DeferredObjective(
                knowledge_point_id=kp_id, note=note
            )
            tx.emit("objective.deferred", {"knowledge_point_id": kp_id})
            return {"knowledge_point_id": kp_id, "deferred": True}

        return self.store.mutate(path_id, fn)


    # -- question bank (M6) ------------------------------------------------
    def list_questions(self, path_id: str, *, tag: str | None = None) -> list[dict[str, Any]]:
        entries = self.store.list_bank_entries(path_id)
        if tag:
            entries = [entry for entry in entries if tag in entry.tags]
        return [entry.model_dump() for entry in entries]

    def tag_question(self, entry_id: str, tags: list[str]) -> dict[str, Any]:
        entry = self.store.get_bank_entry(entry_id)
        if entry is None:
            raise PreconditionError(f"unknown question bank entry: {entry_id}")
        entry.tags = list(dict.fromkeys(str(tag) for tag in tags))
        return self.store.save_bank_entry(entry).model_dump()


def _schedule_after(
    tx,
    kp,
    *,
    result: str,
    hints_used: int,
    review: bool,
    gate_cleared: bool,
    source: str,
    evidence_id: str = "",
) -> None:
    """Seed a new schedule, reschedule a review, or only touch practice time."""
    now = time.time()
    if gate_cleared:
        state = scheduler.initial_state(provenance=source or "system", now=now)
        tx.progress.repetition_states[kp.id] = state
        scheduler.upsert_review_task(
            tx.progress, kp, state, evidence_source="mastery_path", evidence_id=evidence_id
        )
        tx.emit(
            "review.scheduled",
            {
                "knowledge_point_id": kp.id,
                "next_review_at": state.next_review_at,
                "interval_index": state.interval_index,
                "provenance": state.provenance,
            },
        )
    elif review and kp.id in tx.progress.repetition_states:
        state = tx.progress.repetition_states[kp.id]
        scheduler.apply_review(state, result=result, hints_used=hints_used, now=now)
        scheduler.upsert_review_task(
            tx.progress, kp, state, evidence_source="mastery_path", evidence_id=evidence_id
        )
        tx.emit(
            "review.scheduled",
            {
                "knowledge_point_id": kp.id,
                "next_review_at": state.next_review_at,
                "interval_index": state.interval_index,
                "scheduled_after_failure": state.scheduled_after_failure,
            },
        )
    elif kp.id in tx.progress.repetition_states:
        # Practice on an already-mastered objective: touch time, keep anchor.
        scheduler.touch_last_review(tx.progress.repetition_states[kp.id], now=now)


def _public(pending) -> dict[str, Any]:
    from masterypath.learning.pending import public_pending_question

    return public_pending_question(pending)


__all__ = ["LearningService"]
