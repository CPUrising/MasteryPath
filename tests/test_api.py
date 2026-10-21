"""TC-I1..I4 + WS — API contract (spec 05)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from masterypath.agents.llm import FakeLLMClient, LLMResponse, ToolCall
from masterypath.api.app import create_app
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def client(tmp_path):
    store = LearningStore(tmp_path)
    app = create_app(
        store,
        client_factory=lambda: FakeLLMClient(
            [
                LLMResponse(
                    tool_calls=[
                        ToolCall(
                            name="mastery_build",
                            arguments={
                                "modules": [
                                    {
                                        "name": "Basics",
                                        "knowledge_points": [
                                            {"name": "objective", "type": "concept"}
                                        ],
                                    }
                                ]
                            },
                        )
                    ]
                ),
                LLMResponse(text="Outline ready."),
            ]
        ),
    )
    with TestClient(app) as c:
        # A mastery goal exists before its outline: the outline is designed in
        # the goal's first session.
        c.post("/learning/paths", json={"path_id": "p", "goal": "learn X", "name": "X"})
        yield c
    store.close()


def test_tc_i1_map_write_requires_outline_mode(client):
    # switch the session to study first (no outline yet -> refused), so use review
    client.put("/learning/paths/p/sessions/s1/mode", json={"mode": "review"})
    resp = client.put(
        "/learning/paths/p/map",
        params={"session_id": "s1"},
        json={"modules": [{"name": "M", "knowledge_points": [{"name": "obj", "type": "memory"}]}]},
    )
    assert resp.status_code == 409


def test_mode_rejects_unknown_value(client):
    resp = client.put("/learning/paths/p/sessions/s1/mode", json={"mode": "banana"})
    assert resp.status_code == 422


def test_mode_rejects_unknown_path(client):
    resp = client.put("/learning/paths/nope/sessions/s1/mode", json={"mode": "outline"})
    assert resp.status_code == 404


def test_tc_i2_rebuild_requires_confirm(client):
    client.put("/learning/paths/p/sessions/s1/mode", json={"mode": "outline"})
    resp = client.post("/learning/paths/p/rebuild", params={"session_id": "s1"}, json={})
    assert resp.status_code == 409


def test_create_and_read_path(client):
    client.post("/learning/paths", json={"path_id": "p2", "goal": "learn Y", "name": "Y"})
    resp = client.get("/learning/paths/p2")
    assert resp.status_code == 200
    assert resp.json()["goal"] == "learn Y"


def test_outline_mode_allows_map_write(client):
    client.put("/learning/paths/p/sessions/s1/mode", json={"mode": "outline"})
    resp = client.put(
        "/learning/paths/p/map",
        params={"session_id": "s1"},
        json={"modules": [{"name": "M", "knowledge_points": [{"name": "obj", "type": "memory"}]}]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "built"


def test_tc_i4_events_since(client):
    client.put("/learning/paths/p/sessions/s1/mode", json={"mode": "outline"})
    client.put(
        "/learning/paths/p/map",
        params={"session_id": "s1"},
        json={"modules": [{"name": "M", "knowledge_points": [{"name": "obj", "type": "memory"}]}]},
    )
    all_events = client.get("/learning/paths/p/events", params={"since": 0}).json()
    assert any(e["event_type"] == "outline.built" for e in all_events)
    none_after = client.get("/learning/paths/p/events", params={"since": 999}).json()
    assert none_after == []


def test_ws_turn_builds_outline(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"session_id": "s1", "path_id": "p", "mode": "outline", "message": "teach X"})
        seen = []
        while True:
            try:
                seen.append(ws.receive_json())
            except Exception:
                break
    types = [item["type"] for item in seen]
    assert "tool_result" in types and "turn_end" in types
    assert client.get("/learning/paths/p/mastery").status_code == 200
