"""The mastery transport runs through the shared TurnRunner."""

from __future__ import annotations

from fastapi.testclient import TestClient

from masterypath.agents.llm import FakeLLMClient, LLMError, LLMResponse, ToolCall
from masterypath.api.app import create_app
from masterypath.learning.storage import LearningStore


class BoomClient:
    def chat(self, messages, tools):  # noqa: ANN001
        raise LLMError("The configured model was not found at this provider.", code="model_not_found")


class ExplodingClient:
    def chat(self, messages, tools):  # noqa: ANN001
        raise RuntimeError("unexpected provider shape")


def test_ws_mastery_uses_shared_runner(tmp_path):
    store = LearningStore(tmp_path)
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        name="mastery_build",
                        arguments={
                            "modules": [
                                {
                                    "name": "Basics",
                                    "knowledge_points": [{"name": "objective", "type": "memory"}],
                                }
                            ]
                        },
                        id="call-1",
                    )
                ]
            ),
            LLMResponse(text="Outline ready."),
        ]
    )
    app = create_app(store, client_factory=lambda: fake)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"session_id": "s1", "path_id": "p", "mode": "outline", "message": "teach me"}
            )
            types = []
            while True:
                try:
                    types.append(ws.receive_json()["type"])
                except Exception:
                    break
        assert types == ["tool_call", "tool_result", "text_delta", "turn_end"]
        detail = client.get("/learning/sessions/s1").json()
        assert detail["session"]["message_count"] == 2
    store.close()


def test_ws_mastery_maps_llm_error(tmp_path):
    store = LearningStore(tmp_path)
    app = create_app(store, client_factory=lambda: BoomClient())
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"session_id": "s1", "path_id": "p", "mode": "study", "message": "hi"})
            event = ws.receive_json()
    store.close()
    assert event["type"] == "error"
    assert event["data"]["error_code"] == "model_not_found"


def test_ws_mastery_never_drops_the_socket(tmp_path):
    store = LearningStore(tmp_path)
    app = create_app(store, client_factory=lambda: ExplodingClient())
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"session_id": "s1", "path_id": "p", "mode": "study", "message": "hi"})
            event = ws.receive_json()
    store.close()
    assert event["type"] == "error"
    assert event["data"]["error_code"] == "internal_error"


class StubKnowledge:
    def search(self, kb_id, query, *, top_k=4):  # noqa: ANN001
        return [{"source": "gravity.md", "text": "Gravity pulls toward a center.", "score": 1.0}]

    def get(self, kb_id):  # noqa: ANN001
        return {"name": "Physics"}


def test_mastery_runner_injects_knowledge_context(tmp_path):
    from masterypath.agents.turn_runner import TurnRequest, TurnRunner
    from masterypath.chat.service import ChatService
    from masterypath.chat.store import ChatStore
    from masterypath.learning.models import TopicSource
    from masterypath.learning.service import LearningService
    from masterypath.settings.store import SettingsStore

    store = LearningStore(tmp_path)
    service = LearningService(store)
    service.create_path("p", goal="g", name="t")
    service.set_knowledge_base_sources(
        "p",
        [TopicSource(id="kb:k1", kind="knowledge_base", source_id="k1", label="Physics")],
    )
    fake = FakeLLMClient([LLMResponse(text="Answer.")])
    runner = TurnRunner(
        chat_service=ChatService(ChatStore(tmp_path), SettingsStore(tmp_path)),
        learning_service=service,
        store=store,
        client_builder=lambda selection=None, session_key="": fake,
        session_modes={},
        knowledge_service=StubKnowledge(),
    )
    events = list(
        runner.run(
            TurnRequest(
                capability="mastery_path",
                session_id="s1",
                path_id="p",
                mode="outline",
                message="gravity",
            )
        )
    )
    assert [event.type for event in events] == ["text_delta", "turn_end"]
    assert "Reference material" in fake.calls[0][0]["content"]
    assert "gravity.md" in fake.calls[0][0]["content"]
    assert "Current-turn mastery_status snapshot" in fake.calls[0][0]["content"]
    store.close()


def test_ws_mode_switch_emits_session_meta(tmp_path):
    from masterypath.learning.service import LearningService

    store = LearningStore(tmp_path)
    service = LearningService(store)
    service.create_path("p", goal="g", name="t")
    service.build(
        "p",
        {"modules": [{"name": "M", "knowledge_points": [{"name": "fact", "type": "memory"}]}]},
    )
    service.ensure_session("p", "s1", mode="outline")
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        name="mastery_mode",
                        arguments={"mode": "study", "reason": "begin"},
                        id="mode-1",
                    )
                ]
            ),
            LLMResponse(text="Now in study."),
        ]
    )
    app = create_app(store, client_factory=lambda: fake)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"session_id": "s1", "path_id": "p", "mode": "outline", "message": "start"}
            )
            events = []
            while True:
                try:
                    events.append(ws.receive_json())
                except Exception:
                    break
        assert any(
            event["type"] == "session_meta"
            and event["data"]["mastery_session_mode"] == "study"
            for event in events
        )
        assert client.get("/learning/sessions/s1").json()["session"]["mode"] == "study"
    store.close()


def test_create_path_with_knowledge_bases(tmp_path):
    from masterypath.settings.store import SettingsStore
    from masterypath.knowledge.store import KnowledgeStore
    from masterypath.knowledge.service import KnowledgeService

    store = LearningStore(tmp_path)
    settings = SettingsStore(tmp_path)
    kb_service = KnowledgeService(
        KnowledgeStore(tmp_path), settings, embedder_factory=lambda config: (lambda texts: [[0.1] * 4 for _ in texts])
    )
    kb = kb_service.create("Physics")
    app = create_app(store, settings_store=settings)
    with TestClient(app) as client:
        client.post(
            "/learning/paths",
            json={"path_id": "p", "goal": "g", "name": "t", "knowledge_base_ids": [kb["id"]]},
        )
        state = client.get("/learning/paths/p").json()
    store.close()
    assert [item["id"] for item in state["knowledge_bases"]] == [kb["id"]]

