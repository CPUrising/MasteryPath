"""TC-K1..K6, E3 + quantitative gate — study flow (spec 06 §五/六, 03 §E)."""

from __future__ import annotations

import pytest

from masterypath.capabilities.mastery import mode
from masterypath.capabilities.mastery.tools import (
    MasteryGradeTool,
    MasteryQuizTool,
    ToolContext,
)
from masterypath.learning.models import PendingQuestion
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(tmp_path)
    service = LearningService(store)
    service.build(
        "p",
        {
            "modules": [
                {
                    "name": "M",
                    "knowledge_points": [
                        {"name": "fact one", "type": "memory"},
                        {"name": "deep idea", "type": "concept"},
                    ],
                }
            ]
        },
    )
    yield store, service
    store.close()


def _ctx(service, mode_value=mode.STUDY):
    return ToolContext(service=service, path_id="p", session_mode=mode_value)


def test_tc_k1_choice_ok_short_with_options_rejected(env):
    _, service = env
    # invalid first, while no question is open (single-slot would otherwise
    # short-circuit and re-present the existing card instead of validating).
    bad = MasteryQuizTool().execute(
        {
            "knowledge_point_id": "k1",
            "question": "?",
            "question_type": "short",
            "options": [{"label": "A", "body": "x"}],
            "expected_answer": "x",
        },
        _ctx(service),
    )
    assert not bad.ok
    ok = MasteryQuizTool().execute(
        {
            "knowledge_point_id": "k1",
            "question": "2+2?",
            "question_type": "choice",
            "options": [{"label": "A", "body": "3"}, {"label": "B", "body": "4"}],
            "expected_answer": "B",
        },
        _ctx(service),
    )
    assert ok.ok and ok.metadata["status"] == "registered"


def test_tc_k2_single_slot_second_quiz_re_presents(env):
    _, service = env
    ctx = _ctx(service)
    _quiz = MasteryQuizTool()
    first = _quiz.execute(
        {"knowledge_point_id": "k1", "question": "2+2?", "expected_answer": "4"}, ctx
    )
    second = _quiz.execute(
        {"knowledge_point_id": "k1", "question": "other?", "expected_answer": "9"}, ctx
    )
    assert first.metadata["status"] == "registered"
    assert second.metadata["status"] == "already_pending"
    assert second.metadata["question_card"]["prompt"] == "2+2?"


def test_tc_k3_e3_grade_is_idempotent(env):
    store, service = env
    pending = PendingQuestion(
        question_id="q1", knowledge_point_id="k1", question_type="short", expected_answer="4"
    )
    service.register_question("p", pending)
    first = service.grade("p", "q1", "4")
    second = service.grade("p", "q1", "4")
    assert first["status"] == "graded"
    assert second["status"] == "already_graded"
    assert len(store.load("p").learning_evidence) == 1


def test_tc_k4_unparseable_choice_is_ungraded_no_state(env):
    store, service = env
    pending = PendingQuestion(
        question_id="q1",
        knowledge_point_id="k1",
        question_type="choice",
        expected_answer="B",
        options=[{"label": "A", "body": "3"}, {"label": "B", "body": "4"}],  # type: ignore[arg-type]
    )
    service.register_question("p", pending)
    result = service.grade("p", "q1", "zzz")
    assert result["status"] == "ungraded"
    assert store.load("p").mastery_levels.get("k1", 0.0) == 0.0
    assert store.load("p").learning_evidence == []


def test_tc_k5_hints_downgrade_to_partial(env):
    store, service = env
    pending = PendingQuestion(
        question_id="q1", knowledge_point_id="k1", question_type="short", expected_answer="4"
    )
    service.register_question("p", pending)
    result = service.grade("p", "q1", "4", hints_used=1)
    assert result["result"] == "partial"
    assert result["gate_cleared"] is False
    assert not store.load("p").mastery_levels.get("k1")


def test_tc_k6_review_refuses_unmastered(env):
    _, service = env
    result = MasteryQuizTool().execute(
        {"knowledge_point_id": "k1", "question": "?", "expected_answer": "x"},
        _ctx(service, mode.REVIEW),
    )
    assert not result.ok


def test_quantitative_gate_advances_after_correct(env):
    store, service = env
    pending = PendingQuestion(
        question_id="q1", knowledge_point_id="k1", question_type="short", expected_answer="4"
    )
    service.register_question("p", pending)
    result = service.grade("p", "q1", "4")
    assert result["result"] == "correct"
    assert result["gate_cleared"] is True
    assert result["source"] == "system"
    # frontier advances to the concept objective
    assert service.get_state("p")["next"]["knowledge_point_id"] == "k2"


def test_grade_tool_reports_ungraded(env):
    _, service = env
    ctx = _ctx(service)
    MasteryQuizTool().execute(
        {
            "knowledge_point_id": "k1",
            "question": "2+2?",
            "question_type": "choice",
            "options": [{"label": "A", "body": "3"}, {"label": "B", "body": "4"}],
            "expected_answer": "B",
        },
        ctx,
    )
    outcome = MasteryGradeTool().execute(
        {"question_id": _open_id(service), "answer": "zzz"}, ctx
    )
    assert outcome.ok is False
    assert "Not graded" in outcome.content


def _open_id(service):
    interaction = service.store.get_open_interaction("p")
    assert interaction is not None
    return interaction.interaction_id
