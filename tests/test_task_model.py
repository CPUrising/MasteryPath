"""M8 — Task Model suggestions (spec 05 §八)."""

from __future__ import annotations

from masterypath.agents.llm import FakeLLMClient, LLMResponse
from masterypath.agents.task_model import TaskModel
from masterypath.api.app import create_app
from masterypath.learning.storage import LearningStore
from fastapi.testclient import TestClient


def _state(action="practice", name="滑窗计数"):
    return {"next": {"action": action, "knowledge_point_name": name, "knowledge_point_type": "procedure"}}


def test_fallback_without_client():
    model = TaskModel()
    text = model.suggest_question(_state())
    assert text and "滑窗计数" in text


def test_fallback_reflects_action():
    model = TaskModel()
    assert "卡片" in model.suggest_question(_state(action="answer_pending"))
    assert "复习" in model.suggest_question(_state(action="review"))


def test_uses_llm_when_available():
    model = TaskModel(client_factory=lambda: FakeLLMClient([LLMResponse(text="请解释一下滑窗计数")]))
    assert model.suggest_question(_state()) == "请解释一下滑窗计数"


def test_falls_back_when_llm_raises():
    class Boom:
        def chat(self, messages, tools):
            raise RuntimeError("provider down")

    model = TaskModel(client_factory=lambda: Boom())
    assert model.suggest_question(_state())  # non-empty fallback


def test_api_suggest_question(tmp_path):
    store = LearningStore(tmp_path)
    app = create_app(store, client_factory=lambda: FakeLLMClient([]))
    from masterypath.learning.service import LearningService

    service = LearningService(store)
    service.build(
        "p", {"modules": [{"name": "M", "knowledge_points": [{"name": "fact", "type": "memory"}]}]}
    )
    with TestClient(app) as client:
        resp = client.get("/learning/paths/p/suggest-question")
        assert resp.status_code == 200
        assert resp.json()["suggestion"]
    store.close()
