"""Knowledge bases and general chat: storage, vector indexing, SSE turns."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from masterypath.api.app import create_app
from masterypath.learning.storage import LearningStore


def _wait_ready(client: TestClient, kb_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        progress = client.get(f"/knowledge-bases/{kb_id}/progress").json()
        if progress.get("status") not in {"indexing"}:
            return progress
        time.sleep(0.1)
    raise AssertionError("indexing did not finish in time")


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
    assert result["status"] == "indexing"
    assert result["total_files"] == 1

    progress = _wait_ready(env, kb["id"])
    assert progress["status"] == "ready"
    assert progress["percent"] == 1.0

    detail = env.get(f"/knowledge-bases/{kb['id']}").json()
    assert detail["status"] == "ready"
    assert detail["doc_count"] == 1
    assert detail["chunk_count"] > 0

    files = env.get(f"/knowledge-bases/{kb['id']}/files").json()
    assert [item["path"] for item in files] == ["gravity.md"]
    assert files[0]["linked"] is False

    detail = env.get(f"/knowledge-bases/{kb['id']}").json()
    assert detail["embedding_model"]["model_id"] == "e1"
    assert detail["last_indexed_at"]


def test_reindex_requires_documents(env):
    _configure_models(env)
    kb = env.post("/knowledge-bases", json={"name": "Blank"}).json()
    result = env.post(f"/knowledge-bases/{kb['id']}/reindex").json()
    assert result["status"] == "empty"
    progress = env.get(f"/knowledge-bases/{kb['id']}/progress").json()
    assert progress["status"] == "empty"
    assert progress["percent"] is None


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
    assert '"type": "text_delta"' in response.text
    assert '"type": "turn_end"' in response.text

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
    assert _wait_ready(env, kb["id"])["status"] == "ready"

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


# -- indexing progress / upload -------------------------------------------


def test_build_index_reports_file_progress(tmp_path):
    from masterypath.knowledge import indexer
    from masterypath.knowledge.store import KnowledgeStore

    store = KnowledgeStore(tmp_path)
    kb = store.create("Progress")
    raw = store.raw_dir(kb["id"])
    for index in range(3):
        (raw / f"f{index}.md").write_text("word " * 200, encoding="utf-8")
    calls: list[tuple[int, int]] = []
    result = indexer.build_index(
        store,
        kb["id"],
        _fake_embedder(None),
        on_progress=lambda indexed, total: calls.append((indexed, total)),
    )
    assert calls[0] == (0, 3)
    assert calls[-1] == (3, 3)
    assert result["documents"] == 3
    assert result["chunks"] > 0


def test_upload_indexes_and_reports_chunks(env):
    _configure_models(env)
    kb = env.post("/knowledge-bases", json={"name": "Uploads"}).json()
    response = env.post(
        f"/knowledge-bases/{kb['id']}/upload",
        files={"files": ("note.md", b"Binary search halves a sorted list.")},
        data={"paths": json.dumps(["note.md"])},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "indexing"
    assert body["uploaded"] == 1

    progress = _wait_ready(env, kb["id"])
    assert progress["status"] == "ready"
    detail = env.get(f"/knowledge-bases/{kb['id']}").json()
    assert detail["doc_count"] == 1
    assert detail["chunk_count"] > 0


def test_upload_path_traversal_rejected(env):
    _configure_models(env)
    kb = env.post("/knowledge-bases", json={"name": "Safe"}).json()
    response = env.post(
        f"/knowledge-bases/{kb['id']}/upload",
        files={"files": ("evil.md", b"x")},
        data={"paths": json.dumps(["../evil.md"])},
    )
    assert response.status_code == 422


def test_concurrent_reindex_runs_once(tmp_path):
    import threading

    store = LearningStore(tmp_path)

    def slow_embedder(_config):
        def embed(texts: list[str]) -> list[list[float]]:
            time.sleep(0.05)
            return [[1.0] * 4 for _ in texts]
        return embed

    app = create_app(store, embedder_factory=slow_embedder)
    with TestClient(app) as client:
        _configure_models(client)
        kb = client.post("/knowledge-bases", json={"name": "Race"}).json()
        folder = tmp_path / "race"
        folder.mkdir()
        for index in range(4):
            (folder / f"doc{index}.md").write_text("content " * 100, encoding="utf-8")
        first = client.post(
            f"/knowledge-bases/{kb['id']}/folders", json={"folder": str(folder)}
        ).json()
        assert first["status"] == "indexing"
        second = client.post(f"/knowledge-bases/{kb['id']}/reindex").json()
        # The duplicate request returns the SAME run rather than starting another.
        assert second["run_id"] == first["run_id"]
        assert threading.active_count() >= 1
        assert _wait_ready(client, kb["id"])["status"] == "ready"
    store.close()


# -- chunking configuration -----------------------------------------------


def test_global_default_and_kb_override(env):
    _configure_models(env)
    kb = env.post("/knowledge-bases", json={"name": "Chunked"}).json()
    assert kb["effective_config"] == {"chunk_size": 512, "chunk_overlap": 64}
    assert kb["index_config_source"] == "global"

    env.put("/settings/indexing", json={"chunk_size": 800, "chunk_overlap": 100})
    updated = env.get(f"/knowledge-bases/{kb['id']}").json()
    assert updated["effective_config"] == {"chunk_size": 800, "chunk_overlap": 100}
    assert updated["index_config_source"] == "global"

    patched = env.patch(
        f"/knowledge-bases/{kb['id']}",
        json={"chunk_size": 1024, "chunk_overlap": 128},
    ).json()
    assert patched["effective_config"] == {"chunk_size": 1024, "chunk_overlap": 128}
    assert patched["index_config_source"] == "kb"


def test_invalid_chunk_config_rejected(env):
    _configure_models(env)
    bad = env.post(
        "/knowledge-bases", json={"name": "Bad", "chunk_size": 900, "chunk_overlap": 64}
    )
    assert bad.status_code == 422
    kb = env.post("/knowledge-bases", json={"name": "Bad2"}).json()
    overlap_too_large = env.patch(
        f"/knowledge-bases/{kb['id']}", json={"chunk_size": 512, "chunk_overlap": 512}
    )
    assert overlap_too_large.status_code == 422


def test_snapshot_and_needs_reindex(env, tmp_path):
    _configure_models(env)
    kb = env.post(
        "/knowledge-bases",
        json={"name": "Snap", "chunk_size": 512, "chunk_overlap": 64},
    ).json()
    folder = tmp_path / "snap"
    folder.mkdir()
    (folder / "a.md").write_text("content " * 200, encoding="utf-8")
    env.post(f"/knowledge-bases/{kb['id']}/folders", json={"folder": str(folder)})
    assert _wait_ready(env, kb["id"])["status"] == "ready"

    detail = env.get(f"/knowledge-bases/{kb['id']}").json()
    assert detail["indexed_config"]["chunk_size"] == 512
    assert detail["indexed_config"]["chunk_overlap"] == 64
    assert detail["needs_reindex"] is False

    env.patch(
        f"/knowledge-bases/{kb['id']}", json={"chunk_size": 1024, "chunk_overlap": 128}
    )
    changed = env.get(f"/knowledge-bases/{kb['id']}").json()
    assert changed["needs_reindex"] is True


def test_larger_chunk_size_yields_fewer_chunks(env, tmp_path):
    _configure_models(env)
    text = "海运全流程包括订舱、装箱、报关、装船、签发提单。" * 60
    counts: dict[int, int] = {}
    for size, overlap in ((512, 64), (1536, 200)):
        kb = env.post(
            "/knowledge-bases",
            json={"name": f"CS{size}", "chunk_size": size, "chunk_overlap": overlap},
        ).json()
        folder = tmp_path / f"c{size}"
        folder.mkdir()
        (folder / "doc.md").write_text(text, encoding="utf-8")
        env.post(f"/knowledge-bases/{kb['id']}/folders", json={"folder": str(folder)})
        assert _wait_ready(env, kb["id"])["status"] == "ready"
        counts[size] = env.get(f"/knowledge-bases/{kb['id']}").json()["chunk_count"]
    assert counts[512] > counts[1536]
