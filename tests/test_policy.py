"""TC-C1..C17, F1, F6-F9 — gate & navigation (spec 01 §四, 03 §C)."""

from __future__ import annotations

import pytest

from masterypath.learning import policy
from masterypath.learning.models import (
    KnowledgeType,
    QuizAttempt,
)
from masterypath.learning.storage import LearningStore
from tests.factories import kp, module, progress

M = KnowledgeType.MEMORY
P = KnowledgeType.PROCEDURE
C = KnowledgeType.CONCEPT
D = KnowledgeType.DESIGN


def _one(kp_type, **mk):
    p = progress([module("m1", "M1", 0, [kp("k1", "objective", kp_type)])])
    for key, value in mk.items():
        setattr(p, key, value)
    return p, p.modules[0].knowledge_points[0]


def test_tc_c1_memory_below_gate_not_mastered():
    p, k = _one(M, mastery_levels={"k1": 0.85})
    assert not policy.is_assessed_mastered(p, k)
    assert not policy.is_mastered(p, k)


def test_tc_c2_memory_at_gate_mastered():
    p, k = _one(M, mastery_levels={"k1": 0.90})
    assert policy.is_assessed_mastered(p, k)
    assert policy.mastery_source(p, k) == "system"


def test_tc_c3_procedure_full_mastered():
    p, k = _one(P, mastery_levels={"k1": 1.0})
    assert policy.is_mastered(p, k)


def test_tc_c4_concept_score_alone_not_mastered():
    p, k = _one(C, mastery_levels={"k1": 1.0})
    assert not policy.is_mastered(p, k)


def test_tc_c5_concept_qualitative_pass_mastered():
    p, k = _one(C, qualitative_mastery={"k1": True}, mastery_levels={"k1": 0.0})
    assert policy.is_mastered(p, k)


def test_tc_c6_learner_override_mastered_with_learner_source():
    p, k = _one(C)
    p.learner_mastery_overrides["k1"] = {"knowledge_point_id": "k1"}  # type: ignore[assignment]
    assert policy.is_mastered(p, k)
    assert policy.mastery_source(p, k) == "learner"


def test_tc_c7_override_does_not_write_score():
    p, k = _one(M, mastery_levels={"k1": 0.1})
    p.learner_mastery_overrides["k1"] = {"knowledge_point_id": "k1"}  # type: ignore[assignment]
    assert policy.is_mastered(p, k)
    assert p.mastery_levels["k1"] == 0.1  # untouched
    assert not policy.is_assessed_mastered(p, k)


def test_tc_c8_override_produces_no_evidence():
    p, k = _one(C)
    p.learner_mastery_overrides["k1"] = {"knowledge_point_id": "k1"}  # type: ignore[assignment]
    assert p.learning_evidence == []


def test_tc_c9_next_objective_first_unmastered():
    p = progress(
        [
            module(
                "m1",
                "M1",
                0,
                [kp("k1", "first", M), kp("k2", "second", M)],
            )
        ],
        mastery_levels={"k1": 1.0},
    )
    assert policy.next_objective(p).knowledge_point_id == "k2"


def test_tc_c10_all_mastered_is_complete():
    p = progress(
        [module("m1", "M1", 0, [kp("k1", "first", M)])],
        mastery_levels={"k1": 1.0},
    )
    assert policy.next_objective(p).action == "complete"


def test_tc_c11_pending_question_is_answer_pending():
    from masterypath.learning.models import PendingQuestion

    p = progress([module("m1", "M1", 0, [kp("k1", "first", M)])])
    p.pending_question = PendingQuestion(
        question_id="q1", knowledge_point_id="k1", prompt="?"
    )
    assert policy.next_objective(p).action == "answer_pending"


def test_tc_c12_voided_attempt_not_counted():
    p, k = _one(M)
    p.quiz_attempts = [
        QuizAttempt(question_id="q1", knowledge_point_id="k1", is_correct=True),
        QuizAttempt(
            question_id="q2", knowledge_point_id="k1", is_correct=False, voided=True
        ),
    ]
    assert len(policy.active_attempts(p, "k1")) == 1


def test_tc_c13_objective_status_branches():
    p, k = _one(M)
    assert policy.objective_status(p, k) == "new"
    p.quiz_attempts = [QuizAttempt(question_id="q", knowledge_point_id="k1", is_correct=False)]
    assert policy.objective_status(p, k) == "learning"
    p.mastery_levels["k1"] = 1.0
    assert policy.objective_status(p, k) == "mastered"


def test_tc_c14_map_summary_agrees_with_gate():
    p, k = _one(M, mastery_levels={"k1": 0.95})
    summary = policy.map_summary(p)
    assert summary["k1"]["status"] == "mastered"
    assert summary["k1"]["source"] == "system"


def test_tc_c15_deferred_skipped_not_mastered():
    p = progress(
        [
            module(
                "m1",
                "M1",
                0,
                [kp("k1", "first", M), kp("k2", "second", M)],
            )
        ]
    )
    p.deferred_objectives["k1"] = {"knowledge_point_id": "k1"}  # type: ignore[assignment]
    step = policy.next_objective(p)
    assert step.knowledge_point_id == "k2"
    assert not policy.is_mastered(p, p.modules[0].knowledge_points[0])


def test_tc_c16_type_change_refused():
    p, k = _one(C)
    with pytest.raises(ValueError):
        policy.require_type_unchanged(k, D)
    # same type is fine
    policy.require_type_unchanged(k, C)


def test_tc_c17_goal_preserved(tmp_path):
    store = LearningStore(tmp_path)
    store.create(progress([module("m1", "M1", 0, [])], goal="master Rust concurrency"))
    store.mutate("p1", lambda tx: tx.progress.explained_objectives.__setitem__("x", {}))
    assert store.load("p1").goal == "master Rust concurrency"
    store.close()


def test_tc_f1_module_display_target_does_not_gate():
    p = progress(
        [
            module(
                "m1",
                "M1",
                0,
                [kp("k1", "first", M)],
                display_target=0.9,
            )
        ],
        mastery_levels={"k1": 1.0},
    )
    # module aggregate meaningless; all KPs mastered => complete
    assert policy.next_objective(p).action == "complete"


def test_tc_f6_prerequisite_gates():
    p = progress(
        [
            module(
                "m1",
                "M1",
                0,
                [kp("k1", "implement", P), kp("k2", "design", D, prereq=["k1"])],
            )
        ]
    )
    step = policy.next_objective(p)
    assert step.knowledge_point_id == "k1"


def test_tc_f7_prerequisite_mastered_but_design_not_mastered():
    p = progress(
        [
            module(
                "m1",
                "M1",
                0,
                [kp("k1", "implement", P), kp("k2", "design", D, prereq=["k1"])],
            )
        ],
        mastery_levels={"k1": 1.0},
    )
    design = p.modules[0].knowledge_points[1]
    assert not policy.is_mastered(p, design)
    assert policy.next_objective(p).knowledge_point_id == "k2"


def test_tc_f8_prerequisite_and_qualitative_both_required():
    p = progress(
        [
            module(
                "m1",
                "M1",
                0,
                [kp("k1", "implement", P), kp("k2", "design", D, prereq=["k1"])],
            )
        ],
        mastery_levels={"k1": 1.0},
        qualitative_mastery={"k2": True},
    )
    design = p.modules[0].knowledge_points[1]
    assert policy.is_mastered(p, design)
