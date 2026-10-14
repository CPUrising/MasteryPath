"""TC-H1..H5 — deterministic grading (spec 06 §七)."""

from __future__ import annotations

from masterypath.learning.grading import grade, similarity
from masterypath.learning.models import PendingOption, PendingQuestion


def _choice(expected="B"):
    return PendingQuestion(
        question_id="q",
        knowledge_point_id="k",
        question_type="choice",
        expected_answer=expected,
        options=[
            PendingOption(label="A", body="3"),
            PendingOption(label="B", body="4"),
            PendingOption(label="C", body="5"),
        ],
    )


def test_tc_h1_choice_wrong_label_unique_body_matches():
    # learner writes the body instead of the label
    assert grade(_choice("B"), "4").result == "correct"


def test_tc_h2_choice_unparseable_is_ungraded():
    assert grade(_choice("B"), "zzz").result == "ungraded"


def test_tc_h3_short_numeric():
    q = PendingQuestion(question_id="q", knowledge_point_id="k", expected_answer="2")
    assert grade(q, "2.0").result == "correct"
    assert grade(q, "3").result == "incorrect"


def test_tc_h4_short_fuzzy_threshold():
    q = PendingQuestion(question_id="q", knowledge_point_id="k", expected_answer="abcdefghij")
    assert similarity("abcdefghi", "abcdefghij") >= 0.90
    assert grade(q, "abcdefghi").result == "correct"  # sim 0.90
    assert similarity("abcdefgh", "abcdefghij") < 0.90
    assert grade(q, "abcdefgh").result == "incorrect"


def test_tc_h5_open_optional_insufficient_is_partial():
    q = PendingQuestion(
        question_id="q",
        knowledge_point_id="k",
        question_type="open",
        required_keywords=["photosynthesis"],
        optional_keywords=["chlorophyll", "sunlight", "water", "carbon dioxide"],
    )
    # required hit, but only 1/4 optional -> partial
    assert grade(q, "photosynthesis uses chlorophyll").result == "partial"
    # all optional -> correct at grading layer (capped to partial by service)
    assert (
        grade(
            q, "photosynthesis chlorophyll sunlight water carbon dioxide"
        ).result
        == "correct"
    )
