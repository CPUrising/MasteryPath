"""TC-D1..D9 — mode gating & classification guard (spec 02)."""

from __future__ import annotations

import pytest

from masterypath.capabilities.mastery import mode


def test_tc_d1_quiz_refused_in_outline():
    assert mode.tool_is_allowed("mastery_quiz", mode.OUTLINE) is False


def test_tc_d2_build_refused_in_study():
    assert mode.tool_is_allowed("mastery_build", mode.STUDY) is False


def test_tc_d3_shared_tool_allowed():
    assert mode.tool_is_allowed("mastery_status", mode.STUDY) is True


def test_tc_d4_missing_mode_enforces_nothing():
    assert mode.tool_is_allowed("mastery_build", None) is True
    assert mode.tool_is_allowed("mastery_quiz", "") is True
    assert mode.tool_is_allowed("mastery_quiz", "bogus") is True


def test_tc_d5_study_without_outline_refused():
    assert mode.admission_error(mode.STUDY, has_outline=False) != ""


def test_tc_d6_study_with_outline_allowed():
    assert mode.admission_error(mode.STUDY, has_outline=True) == ""


def test_tc_d7_review_scope_helpers():
    # owning_modes is what the quiz/grade scope check consults.
    assert set(mode.owning_modes("mastery_quiz")) == {mode.STUDY, mode.REVIEW}
    assert mode.tool_is_allowed("mastery_quiz", mode.REVIEW) is True
    assert mode.tool_is_allowed("mastery_quiz", mode.OUTLINE) is False


def test_tc_d8_review_allows_mastered_gate_tools():
    assert mode.tool_is_allowed("mastery_assess", mode.REVIEW) is True


def test_tc_d9_classification_complete_and_fail_closed():
    # full set is complete
    mode.assert_classification_complete()
    # a stray tool is rejected (fail-closed)
    with pytest.raises(AssertionError):
        mode.assert_classification_complete(
            mode.all_mastery_tools() | {"mystery_tool"}
        )


def test_every_mounted_tool_is_classified():
    from masterypath.capabilities.mastery.tools import TOOLS

    mode.assert_classification_complete(set(TOOLS))


def test_status_and_mode_are_shared_in_every_mode():
    for tool in ("mastery_status", "mastery_mode"):
        for current in mode.MODES:
            assert mode.tool_is_allowed(tool, current) is True


def test_wrong_mode_message_names_target():
    message = mode.wrong_mode_message("mastery_quiz", mode.OUTLINE)
    assert "mastery_mode" in message
    assert "'study'" in message
