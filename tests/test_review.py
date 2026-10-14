"""M5 — review scheduling integration (spec 04)."""

from __future__ import annotations

import pytest

from masterypath.learning.models import PendingQuestion
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(tmp_path)
    service = LearningService(store)
    service.build(
        "p",
        {"modules": [{"name": "M", "knowledge_points": [{"name": "fact", "type": "memory"}]}]},
    )
    yield store, service
    store.close()


def _master(service, question_id="q1", answer="4"):
    pending = PendingQuestion(
        question_id=question_id, knowledge_point_id="k1", question_type="short", expected_answer="4"
    )
    service.register_question("p", pending)
    return service.grade("p", question_id, answer)


def _make_due(store):
    def fn(tx):
        state = tx.progress.repetition_states["k1"]
        state.next_review_at = 0.0
        for task in tx.progress.review_queue:
            task.due_at = 0.0

    store.mutate("p", fn)


def test_mastering_seeds_schedule_and_emits(env):
    store, service = env
    _master(service)
    progress = store.load("p")
    assert "k1" in progress.repetition_states
    assert progress.review_queue and progress.review_queue[0].knowledge_point_id == "k1"
    events = [e["event_type"] for e in store.events_since("p", 0)]
    assert "review.scheduled" in events and "objective.mastered" in events


def test_due_review_becomes_next_action(env):
    store, service = env
    _master(service)
    _make_due(store)
    step = service.get_state("p")["next"]
    assert step["action"] == "review"
    assert step["knowledge_point_id"] == "k1"


def test_review_correct_reschedules_forward(env):
    store, service = env
    _master(service)
    _make_due(store)
    # second question in review mode
    pending = PendingQuestion(
        question_id="q2", knowledge_point_id="k1", question_type="short", expected_answer="4"
    )
    service.register_question("p", pending)
    result = service.grade("p", "q2", "4", review=True)
    assert result["result"] == "correct"
    state = store.load("p").repetition_states["k1"]
    assert state.interval_index >= 2
    assert state.scheduled_after_failure is False
    assert state.next_review_at > 0


def test_review_failure_sets_flag_and_relearning(env):
    store, service = env
    _master(service)
    _make_due(store)
    pending = PendingQuestion(
        question_id="q2", knowledge_point_id="k1", question_type="short", expected_answer="4"
    )
    service.register_question("p", pending)
    service.grade("p", "q2", "9", review=True)
    state = store.load("p").repetition_states["k1"]
    assert state.scheduled_after_failure is True
    assert state.lapse_count == 1


def test_learner_override_seeds_shorter_interval(env):
    store, service = env
    service.override_mastery("p", "k1", note="I know this")
    state = store.load("p").repetition_states["k1"]
    assert state.provenance == "learner"
    first_interval_days = (state.next_review_at - state.last_scheduled_at) / 86400.0
    assert 0.3 <= first_interval_days <= 0.7
