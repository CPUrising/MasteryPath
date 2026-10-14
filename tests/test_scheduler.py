"""TC-G1..G5 — SM-2 arithmetic & anchor semantics (spec 04)."""

from __future__ import annotations

from masterypath.learning import scheduler


def test_tc_g1_interval_sequence():
    ef = scheduler.DEFAULT_EF
    assert [scheduler.interval_days(i, ef) for i in (1, 2, 3, 4, 5)] == [1, 6, 15, 38, 95]


def test_tc_g2_failure_enters_relearning():
    state = scheduler.initial_state(provenance="system", now=1000.0)
    scheduler.apply_review(state, result="incorrect", now=2000.0)
    assert state.scheduled_after_failure is True
    assert state.lapse_count == 1
    assert state.interval_index == 0
    assert state.next_review_at - 2000.0 <= scheduler.SECONDS_PER_DAY


def test_tc_g3_success_after_failure_clears_flag():
    state = scheduler.initial_state(provenance="system", now=1000.0)
    scheduler.apply_review(state, result="incorrect", now=2000.0)
    scheduler.apply_review(state, result="correct", now=3000.0)
    assert state.scheduled_after_failure is False
    assert state.interval_index == 1
    expected = 3000.0 + scheduler.interval_days(1, state.ease_factor) * scheduler.SECONDS_PER_DAY
    assert state.next_review_at == expected


def test_tc_g4_in_session_practice_keeps_anchor():
    state = scheduler.initial_state(provenance="system", now=1000.0)
    anchor = state.next_review_at
    scheduler.touch_last_review(state, now=5000.0)
    assert state.next_review_at == anchor
    assert state.last_review_at == 5000.0
    assert state.scheduled_after_failure is False


def test_tc_g5_learner_first_interval_shorter():
    system_state = scheduler.initial_state(provenance="system", now=0.0)
    learner_state = scheduler.initial_state(provenance="learner", now=0.0)
    ratio = learner_state.next_review_at / system_state.next_review_at
    assert 0.3 <= ratio <= 0.7


def test_ease_factor_floor():
    assert scheduler.update_ease(scheduler.DEFAULT_EF, 0) >= scheduler.MIN_EF
    assert scheduler.update_ease(1.3, 0) == 1.3
