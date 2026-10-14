"""TC-E1/E2/E4 — interaction single-slot & public projection (spec 03 §E)."""

from __future__ import annotations

import pytest

from masterypath.learning.models import (
    InteractionStatus,
    MasteryInteraction,
    PendingQuestion,
)
from masterypath.learning.pending import public_pending_question
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def store(tmp_path):
    s = LearningStore(tmp_path)
    yield s
    s.close()


def _interaction(path_id: str, qid: str, iid: str) -> MasteryInteraction:
    return MasteryInteraction(
        interaction_id=iid,
        path_id=path_id,
        question=PendingQuestion(
            question_id=qid,
            knowledge_point_id="k1",
            prompt="2+2?",
            question_type="short",
            expected_answer="4",
            explanation="sum",
        ),
    )


def test_tc_e1_single_open_slot(store):
    store.save_interaction(_interaction("p", "q1", "i1"))
    open_one = store.get_open_interaction("p")
    assert open_one is not None and open_one.interaction_id == "i1"
    # make it terminal
    open_one.status = InteractionStatus.GRADED
    store.save_interaction(open_one)
    assert store.get_open_interaction("p") is None


def test_tc_e2_after_graded_new_question_is_open(store):
    first = _interaction("p", "q1", "i1")
    first.status = InteractionStatus.GRADED
    store.save_interaction(first)
    store.save_interaction(_interaction("p", "q2", "i2"))
    assert store.get_open_interaction("p").interaction_id == "i2"


def test_tc_e4_public_projection_hides_answer():
    pending = PendingQuestion(
        question_id="q1",
        knowledge_point_id="k1",
        prompt="2+2?",
        question_type="short",
        expected_answer="4",
        explanation="sum",
    )
    public = public_pending_question(pending)
    assert "expected_answer" not in public
    assert "explanation" not in public
    assert public["prompt"] == "2+2?"
