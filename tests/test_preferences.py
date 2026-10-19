"""Session preferences, migration, WS error events, KB-source preservation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from masterypath.api.app import create_app
from masterypath.chat.store import ChatStore
from masterypath.learning.models import TopicSource
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


def test_learning_session_preferences_persist(tmp_path):
    store = LearningStore(tmp_path)
    store.upsert_session({"session_id": "s1", "path_id": "p", "mode": "study"})
    store.set_session_preferences("s1", {"llm_selection": {"provider_id": "x", "model_id": "m"}})
    store.close()

    reopened = LearningStore(tmp_path)
    session = reopened.get_session("s1")
    assert session["preferences"]["llm_selection"] == {"provider_id": "x", "model_id": "m"}
    # Idempotent migration: a second open must not fail or duplicate the column.
    reopened._migrate()
    reopened.close()


def test_chat_session_preferences_and_legacy_model_id(tmp_path):
    store = ChatStore(tmp_path)
    session = store.create_session(preferences={"llm_selection": {"provider_id": "p", "model_id": "m1"}})
    assert session["preferences"]["llm_selection"]["model_id"] == "m1"
    updated = store.update_session(
        session["session_id"], {"preferences": {"knowledge_bases": ["kb-1"]}}
    )
    assert updated["preferences"]["knowledge_bases"] == ["kb-1"]
    # llm_selection survives a later partial update and stays mirrored to model_id.
    assert updated["model_id"] == "m1"
    assert updated["preferences"]["llm_selection"]["model_id"] == "m1"
    store.close()


def test_ws_reports_structured_error_when_no_model(tmp_path):
    store = LearningStore(tmp_path)
    app = create_app(store)  # no llm configured
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"session_id": "s1", "path_id": "p", "mode": "study", "message": "hi"}
            )
            event = ws.receive_json()
    store.close()
    assert event["type"] == "error"
    assert event["data"]["error_code"] == "bad_request"
    assert event["data"]["retryable"] is False
    assert event["data"]["message"]


def test_knowledge_base_sources_preserve_other_kinds(tmp_path):
    store = LearningStore(tmp_path)
    service = LearningService(store)
    service.create_path("p", goal="g", name="t")
    service.attach_sources(
        "p", [TopicSource(id="src:a.md", kind="file", source_id="a.md", label="a.md")]
    )
    service.set_knowledge_base_sources(
        "p",
        [
            TopicSource(id="kb:k1", kind="knowledge_base", source_id="k1", label="K1"),
            TopicSource(id="kb:k2", kind="knowledge_base", source_id="k2", label="K2"),
        ],
    )
    state = service.get_state("p")
    kinds = {source["kind"] for source in state["sources"]}
    assert "file" in kinds
    assert [kb["id"] for kb in state["knowledge_bases"]] == ["k1", "k2"]

    service.set_knowledge_base_sources("p", [])
    state = service.get_state("p")
    assert state["knowledge_bases"] == []
    assert any(source["kind"] == "file" for source in state["sources"])
    store.close()
