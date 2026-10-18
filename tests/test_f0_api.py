"""F0 backend — settings, sessions, dashboard fields, lifecycle, REST study."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from masterypath.agents.llm import FakeLLMClient, LLMResponse
from masterypath.api.app import create_app
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


def _build(service):
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


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(tmp_path)
    service = LearningService(store)
    _build(service)
    app = create_app(
        store,
        client_factory=lambda: FakeLLMClient([LLMResponse(text="你好，我们开始吧。")]),
    )
    with TestClient(app) as client:
        yield client, store, service
    store.close()


def test_settings_roundtrip(env):
    client, _, _ = env
    assert client.get("/settings/llm").json() == {"models": [], "active_id": ""}
    providers = [
        {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com", "api_key": "sk-x"}
    ]
    assert client.put("/settings/providers", json=providers).json() == providers
    assert client.get("/settings/providers").json() == providers
    assert client.get("/settings/nope").status_code == 404


def test_model_section_list_roundtrip(env):
    client, _, _ = env
    section = {
        "models": [
            {"id": "m1", "provider_id": "deepseek", "model": "deepseek-chat", "name": "Chat"}
        ],
        "active_id": "m1",
    }
    assert client.put("/settings/llm", json=section).json() == section
    assert client.get("/settings/llm").json() == section
    # legacy single-selection shape folds into a one-entry list
    legacy = client.put("/settings/embedding", json={"provider": "ollama", "model": "bge-m3"}).json()
    assert legacy["models"][0]["model"] == "bge-m3"


def test_dashboard_fields(env):
    client, _, _ = env
    state = client.get("/learning/paths/p").json()
    assert state["counts"]["total"] == 2
    assert state["review_settings"] == {"desired_retention": 0.9, "scope": "path"}
    assert state["session_count"] == 0
    assert "reviews" in state and state["learner_profile"] is None


def test_review_settings_update(env):
    client, store, _ = env
    assert client.put("/learning/paths/p/review-settings", json={"desired_retention": 0.95}).json()[
        "desired_retention"
    ] == 0.95
    assert store.load("p").desired_retention == 0.95


def test_rename_redo_delete(env):
    client, store, _ = env
    assert client.patch("/learning/paths/p", json={"name": "重命名"}).json()["name"] == "重命名"
    assert store.load("p").name == "重命名"
    # master something then reset
    service = LearningService(store)
    service.override_mastery("p", "k1")
    assert store.load("p").learner_mastery_overrides
    assert client.post("/learning/paths/p/redo").json()["status"] == "reset"
    assert store.load("p").learner_mastery_overrides == {}
    assert client.delete("/learning/paths/p").status_code == 204
    assert client.get("/learning/paths/p").status_code == 404


def test_rest_quiz_and_grade(env):
    client, _, _ = env
    quiz = client.post(
        "/learning/paths/p/quiz",
        json={"knowledge_point_id": "k1", "question": "2+2?", "expected_answer": "4", "session_id": "s1"},
    ).json()
    assert quiz["status"] == "registered"
    question_id = quiz["question_id"]
    graded = client.post(
        "/learning/paths/p/grade", json={"question_id": question_id, "answer": "4"}
    ).json()
    assert graded["status"] == "graded" and graded["result"] == "correct"
    assert graded["gate_cleared"] is True


def test_rest_assess_and_skip(env):
    client, _, _ = env
    assessed = client.post(
        "/learning/paths/p/assess",
        json={"knowledge_point_id": "k2", "passed": True, "evidence": "用自己的话解释了"},
    ).json()
    assert assessed["passed"] is True
    quiz = client.post(
        "/learning/paths/p/quiz",
        json={"knowledge_point_id": "k1", "question": "?", "expected_answer": "x", "session_id": "s1"},
    ).json()
    assert client.post(
        "/learning/paths/p/skip-question", json={"question_id": quiz["question_id"]}
    ).json()["status"] == "abandoned"


def test_sessions_and_mode(env):
    client, _, _ = env
    client.put("/learning/paths/p/sessions/s1/mode", json={"mode": "outline", "actor": "learner"})
    sessions = client.get("/learning/paths/p/sessions").json()["sessions"]
    assert len(sessions) == 1 and sessions[0]["mode"] == "outline"
    detail = client.get("/learning/sessions/s1").json()
    assert detail["session"]["session_id"] == "s1" and detail["messages"] == []


def test_cors_allows_frontend_origin(env):
    client, _, _ = env
    resp = client.get("/learning/paths", headers={"Origin": "http://localhost:3000"})
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_ws_turn_persists_session(env):
    client, _, _ = env
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"session_id": "s9", "path_id": "p", "mode": "study", "message": "开始学习"})
        while True:
            try:
                ws.receive_json()
            except Exception:
                break
    detail = client.get("/learning/sessions/s9").json()
    assert detail["session"]["message_count"] == 2
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
