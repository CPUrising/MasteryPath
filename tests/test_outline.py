"""TC-J1..J6, F2..F5 — outline build/revise & gaps (spec 06 §二..四, §八)."""

from __future__ import annotations

import pytest

from masterypath.learning.outline import OutlineError
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def store(tmp_path):
    s = LearningStore(tmp_path)
    yield s
    s.close()


def _payload(*modules):
    return {"modules": list(modules)}


def test_tc_j1_build_empty_path(store):
    service = LearningService(store)
    result = service.build(
        "p",
        _payload(
            {
                "name": "Basics",
                "knowledge_points": [
                    {"name": "objective one", "type": "concept"},
                    {"name": "objective two", "type": "memory"},
                ],
            }
        ),
    )
    assert result.status == "built"
    assert len(result.modules) == 1
    assert len(result.modules[0].knowledge_points) == 2
    events = store.events_since("p", 0)
    assert events[-1]["event_type"] == "outline.built"


def test_tc_j2_rebuild_without_confirm_refused(store):
    service = LearningService(store)
    service.build(
        "p",
        _payload({"name": "A", "knowledge_points": [{"name": "one", "type": "memory"}]}),
    )
    result = service.build(
        "p",
        _payload({"name": "B", "knowledge_points": [{"name": "two", "type": "memory"}]}),
    )
    assert result.status == "refused_rebuild"
    assert result.dropped  # lists what would be lost
    assert len(service.get_state("p")["map"]) == 1  # unchanged


def test_tc_j2b_rebuild_with_confirm_replaces(store):
    service = LearningService(store)
    service.build(
        "p",
        _payload({"name": "A", "knowledge_points": [{"name": "one", "type": "memory"}]}),
    )
    result = service.build(
        "p",
        _payload({"name": "B", "knowledge_points": [{"name": "two", "type": "memory"}]}),
        confirm=True,
    )
    assert result.status == "built" and result.rebuilt
    assert list(service.get_state("p")["map"]) == ["k1"]
    assert store.events_since("p", 0)[-1]["event_type"] == "path.rebuilt"


def test_tc_j3_duplicate_name_rejected(store):
    service = LearningService(store)
    with pytest.raises(OutlineError):
        service.build(
            "p",
            _payload(
                {
                    "name": "A",
                    "knowledge_points": [
                        {"name": "same name", "type": "memory"},
                        {"name": "same name", "type": "concept"},
                    ],
                }
            ),
        )


def test_tc_j4_revise_preserves_untouched_progress(store):
    service = LearningService(store)
    service.build(
        "p",
        _payload(
            {
                "name": "A",
                "knowledge_points": [
                    {"name": "keep me", "type": "memory"},
                    {"name": "also here", "type": "concept"},
                ],
            }
        ),
    )
    store.mutate("p", lambda tx: tx.progress.mastery_levels.__setitem__("k1", 1.0))
    result = service.revise(
        "p", [{"op": "add_kp", "module_id": "m1", "name": "brand new", "type": "procedure"}]
    )
    assert result.status == "revised"
    assert store.load("p").mastery_levels.get("k1") == 1.0
    assert store.events_since("p", 0)[-1]["event_type"] == "outline.revised"


def test_tc_j5_revise_type_change_refused(store):
    service = LearningService(store)
    service.build(
        "p", _payload({"name": "A", "knowledge_points": [{"name": "one", "type": "concept"}]})
    )
    with pytest.raises(OutlineError):
        service.revise("p", [{"op": "update_kp", "kp_id": "k1", "type": "memory"}])


def test_tc_j6_build_reports_gaps(store):
    service = LearningService(store)
    result = service.build(
        "p", _payload({"name": "A", "knowledge_points": [{"name": "no source", "type": "concept"}]})
    )
    assert result.gaps
    assert all(gap.kind.value == "goal_gap" for gap in result.gaps)


def test_tc_f2_regenerate_does_not_close_coverage_gap(store):
    service = LearningService(store)
    modules = {"name": "A", "knowledge_points": [{"name": "no source", "type": "concept"}]}
    service.build("p", _payload(modules))
    result = service.build("p", _payload(modules), confirm=True)  # regenerate
    assert result.gaps  # the source is still absent -> gap persists


def test_tc_f3_source_omission_closes_when_used(store):
    service = LearningService(
        store, source_map={"a.txt": "s1"}, selected_source_ids={"s1"}
    )
    # module does not use a.txt -> omission gap
    first = service.build(
        "p", _payload({"name": "A", "knowledge_points": [{"name": "obj", "type": "concept", "sources": []}]})
    )
    # KPs default to ungrounded; a.txt is omitted
    assert any(g.kind.value == "source_omission" for g in first.gaps)
    # rebuild using the material -> omission closes
    second = service.build(
        "p",
        _payload(
            {
                "name": "A",
                "materials": ["a.txt"],
                "knowledge_points": [{"name": "obj", "type": "concept"}],
            }
        ),
        confirm=True,
    )
    assert not any(g.kind.value == "source_omission" for g in second.gaps)


def test_tc_f4_accept_gap_and_resolve(store):
    service = LearningService(store)
    result = service.build(
        "p", _payload({"name": "A", "knowledge_points": [{"name": "no source", "type": "concept"}]})
    )
    gap_id = result.gaps[0].id
    service.resolve_gap("p", gap_id, "accept")
    state = service.get_state("p")
    resolved = {g["id"]: g for g in state["gaps"]}
    assert resolved[gap_id]["resolution"] == "accepted"
    assert state["map"]["k1"]["grounding"] == "ungrounded"
    assert store.events_since("p", 0)[-1]["event_type"] == "gap.resolved"
