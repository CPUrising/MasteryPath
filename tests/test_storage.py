"""TC-B1..B17 — storage, CAS, events, concurrency (spec 03 §B)."""

from __future__ import annotations

import threading

import pytest

from masterypath.learning.models import LearningProgress
from masterypath.learning.storage import (
    ConcurrentModificationError,
    LearningStore,
    PreconditionError,
)


@pytest.fixture()
def store(tmp_path):
    s = LearningStore(tmp_path)
    yield s
    s.close()


def test_tc_b1_load_missing_returns_none_and_creates_nothing(store):
    assert store.load("ghost") is None
    assert store.list_paths() == []


def test_tc_b2_create_then_load(tmp_path):
    store = LearningStore(tmp_path)
    store.create(LearningProgress(path_id="p", name="P"))
    loaded = store.load("p")
    assert loaded is not None and loaded.name == "P"
    store.close()


def test_tc_b3_mutate_bumps_version(store):
    store.create(LearningProgress(path_id="p"))
    store.mutate("p", lambda tx: tx.progress.explained_objectives.__setitem__("k", {}))
    assert store.load("p").version == 2


def test_tc_b4_stale_expected_version_rejected(store):
    store.create(LearningProgress(path_id="p"))
    store.mutate("p", lambda tx: None)  # version -> 2
    with pytest.raises(PreconditionError):
        store.mutate("p", lambda tx: None, expected_version=1)
    assert store.load("p").version == 2


def test_tc_b5_b15_exception_rolls_back_state_and_events(store):
    store.create(LearningProgress(path_id="p"))

    def boom(tx):
        tx.progress.explained_objectives["k"] = {}
        tx.emit("objective.explained", {"knowledge_point_id": "k"})
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        store.mutate("p", boom)
    assert store.load("p").version == 1
    assert store.events_since("p", 0) == []


def test_tc_b6_b17_workspace_isolation(tmp_path):
    a = LearningStore(tmp_path / "ws_a")
    b = LearningStore(tmp_path / "ws_b")
    a.create(LearningProgress(path_id="p", name="A"))
    b.create(LearningProgress(path_id="p", name="B"))
    assert a.load("p").name == "A"
    assert b.load("p").name == "B"
    a.close()
    b.close()


def test_tc_b7_events_carry_path_and_revision(store):
    store.create(LearningProgress(path_id="p"))

    def fn(tx):
        tx.progress.explained_objectives["k"] = {"summary": "x"}
        tx.emit("objective.explained", {"knowledge_point_id": "k"})

    store.mutate("p", fn)
    events = store.events_since("p", 0)
    assert len(events) == 1
    assert events[0]["path_id"] == "p"
    assert events[0]["revision"] == 2


def test_tc_b8_events_append_only(store):
    store.create(LearningProgress(path_id="p"))
    store.mutate("p", lambda tx: tx.emit("e1", {}))
    store.mutate("p", lambda tx: tx.emit("e2", {}))
    events = store.events_since("p", 0)
    assert [e["event_type"] for e in events] == ["e1", "e2"]


def test_tc_b9_mergeable_concurrent_writes_all_apply(store):
    store.create(LearningProgress(path_id="p"))

    def worker(key):
        store.mutate("p", lambda tx: tx.progress.explained_objectives.__setitem__(key, {}))

    threads = [threading.Thread(target=worker, args=(f"k{i}",)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert set(store.load("p").explained_objectives) == {f"k{i}" for i in range(6)}


def test_tc_b10_precondition_error_not_retried_and_no_write(store):
    store.create(LearningProgress(path_id="p"))

    def fail(tx):
        tx.progress.explained_objectives["k"] = {}
        tx.require(False, "precondition not met")

    with pytest.raises(PreconditionError):
        store.mutate("p", fail)
    assert store.load("p").version == 1
    assert store.events_since("p", 0) == []


def test_tc_b11_cas_exhaustion_raises_concurrent(monkeypatch, store):
    store.create(LearningProgress(path_id="p"))

    def always_conflict(*args, **kwargs):
        raise ConcurrentModificationError("forced")

    monkeypatch.setattr(store, "_attempt", always_conflict)
    with pytest.raises(ConcurrentModificationError):
        store.mutate("p", lambda tx: None)


def test_tc_b12_concurrent_different_paths(store):
    store.create(LearningProgress(path_id="a"))
    store.create(LearningProgress(path_id="b"))
    errors: list[Exception] = []

    def worker(path_id, key):
        try:
            store.mutate(path_id, lambda tx: tx.progress.explained_objectives.__setitem__(key, {}))
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=("a", "ka")),
        threading.Thread(target=worker, args=("b", "kb")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert set(store.load("a").explained_objectives) == {"ka"}
    assert set(store.load("b").explained_objectives) == {"kb"}


def test_tc_b16_turn_mutates_two_paths(store):
    store.create(LearningProgress(path_id="p1"))
    store.create(LearningProgress(path_id="p2"))
    store.mutate("p1", lambda tx: tx.emit("switch", {}))
    store.mutate("p2", lambda tx: tx.emit("switch", {}))
    assert store.load("p1").version == 2
    assert store.load("p2").version == 2


def test_tc_b14_wal_enabled(store):
    mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
