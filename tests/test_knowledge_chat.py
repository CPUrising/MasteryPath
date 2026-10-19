"""Knowledge bases and general chat: storage, vector indexing, SSE turns."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from masterypath.api.app import create_app
from masterypath.learning.storage import LearningStore


def _fake_embedder(_config):
    def embed(texts: list[str]) -> list[list[float]]:
        return [
            [float((abs(hash(text)) >> (i * 4)) % 13) for i in range(8)]
            for text in texts
        ]

    return embed


class FakeStreamClient:
    """Records the prompt and streams a canned answer."""

    last_messages: list[dict] = []

    def __init__(self, _config):
        self.config = _config

    def stream_chat(self, messages):
        type(self).last_messages = messages
        yield "Hello "
        yield "learner"


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(tmp_path)
    app = create_app(
        store,
        embedder_factory=_fake_embedder,
        chat_client_factory=lambda config: FakeStreamClient(config),
    )
    with TestClient(app) as client:
        yield client
    store.close()


def _configure_models(client: TestClient) -> None:
    client.put(
        "/settings/providers",
        json=[
            {
                "id": "ollama",
                "name": "Ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "api_key": "",
                "protocol": "ollama",
            }
        ],
    )
    client.put(
        "/settings/embedding",
        json={
            "models": [
                {
                    "id": "e1",
                    "provider_id": "ollama",
                    "model": "bge-m3:latest",
                    "name": "bge-m3:latest",
                    "dimension": 1024,
                }
            ],
            "active_id": "e1",
        },
    )
    client.put(
        "/settings/llm",
        json={
            "models": [
                {"id": "m1", "provider_id": "ollama", "model": "qwen", "name": "qwen"}
            ],
            "active_id": "m1",
        },
    )


# -- knowledge bases -------------------------------------------------------


def test_create_without_embedding_is_prerequisite_missing(env):
    created = env.post("/knowledge-bases", json={"name": "Empty KB"}).json()
    assert created["status"] == "rag_prerequisite_missing"
    assert created["id"] == "Empty-KB"
    assert env.get("/knowledge-bases").json()[0]["name"] == "Empty KB"


def test_import_index_and_search(env, tmp_path):
    _configure_models(env)
    kb = env.post("/knowledge-bases", json={"name": "Physics"}).json()
    assert kb["status"] == "empty"

    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "gravity.md").write_text(
        "Gravity is the force by which a planet draws objects toward its center.",
        encoding="utf-8",
    )
    result = env.post(
        f"/knowledge-bases/{kb['id']}/folders", json={"folder": str(folder)}
    ).json()
    assert result["status"] == "ready"
    assert result["doc_count"] == 1

    files = env.get(f"/knowledge-bases/{kb['id']}/files").json()
    assert [item["path"] for item in files] == ["gravity.md"]

    detail = env.get(f"/knowledge-bases/{kb['id']}").json()
    assert detail["embedding_model"]["model_id"] == "e1"
    assert detail["last_indexed_at"]


def test_reindex_requires_documents(env):
    _configure_models(env)
    kb = env.post("/knowledge-bases", json={"name": "Blank"}).json()
    result = env.post(f"/knowledge-bases/{kb['id']}/reindex").json()
    assert result["status"] == "error"
    assert "no readable documents" in result["error"]


def test_delete_and_unknown(env):
    kb = env.post("/knowledge-bases", json={"name": "Temp"}).json()
    assert env.delete(f"/knowledge-bases/{kb['id']}").status_code == 204
    assert env.get(f"/knowledge-bases/{kb['id']}").status_code == 404
    # A traversal-shaped id is rejected by the safe-id gate.
    assert env.get("/knowledge-bases/..%2F..%2Fdata").status_code == 404


# -- chat ------------------------------------------------------------------


def test_chat_stream_persists_messages(env):
    _configure_models(env)
    session = env.post("/chat/sessions", json={}).json()
    response = env.post(
        f"/chat/sessions/{session['session_id']}/turns",
        json={"message": "What is gravity?"},
    )
    assert response.status_code == 200
    assert '"type": "delta"' in response.text
    assert '"type": "done"' in response.text

    detail = env.get(f"/chat/sessions/{session['session_id']}").json()
    roles = [message["role"] for message in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "Hello learner"
    assert detail["session"]["title"] == "What is gravity?"


def test_chat_injects_knowledge_context(env, tmp_path):
    _configure_models(env)
    kb = env.post("/knowledge-bases", json={"name": "Physics"}).json()
    folder = tmp_path / "notes"
    folder.mkdir()
    (folder / "gravity.md").write_text(
        "Gravity draws objects toward a center.", encoding="utf-8"
    )
    env.post(f"/knowledge-bases/{kb['id']}/folders", json={"folder": str(folder)})

    session = env.post("/chat/sessions", json={"kb_ids": [kb["id"]]}).json()
    env.post(f"/chat/sessions/{session['session_id']}/turns", json={"message": "gravity"})
    prompt = " ".join(item["content"] for item in FakeStreamClient.last_messages)
    assert "Reference material" in prompt
    assert "gravity.md" in prompt


def test_chat_without_model_reports_error(env):
    session = env.post("/chat/sessions", json={}).json()
    response = env.post(
        f"/chat/sessions/{session['session_id']}/turns", json={"message": "hi"}
    )
    assert '"type": "error"' in response.text
    assert "No language model" in response.text


# -- question bank ---------------------------------------------------------


def test_global_question_bank(env):
    env.post("/learning/paths", json={"path_id": "p1", "goal": "g", "name": "Topic"})
    env.put("/learning/paths/p1/sessions/s1/mode", json={"mode": "outline"})
    env.put(
        "/learning/paths/p1/map",
        params={"session_id": "s1"},
        json={
            "modules": [
                {
                    "name": "M",
                    "knowledge_points": [{"name": "fact one", "type": "memory"}],
                }
            ],
            "confirm": True,
        },
    )
    state = env.get("/learning/paths/p1").json()
    kp_id = next(iter(state["map"]))
    env.put("/learning/paths/p1/sessions/s1/mode", json={"mode": "study"})
    quiz = env.post(
        "/learning/paths/p1/quiz",
        json={
            "knowledge_point_id": kp_id,
            "question": "2+2?",
            "expected_answer": "4",
            "session_id": "s1",
        },
    ).json()
    env.post(
        "/learning/paths/p1/grade",
        json={"question_id": quiz["question_id"], "answer": "4"},
    )
    rows = env.get("/questions").json()
    assert rows and rows[0]["path_name"] == "Topic"
    assert rows[0]["question"] == "2+2?"
