"""M6 — question bank sync & tags (spec 06/05)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from masterypath.api.app import create_app
from masterypath.learning.models import PendingQuestion
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(tmp_path)
    service = LearningService(store)
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
    yield store, service
    store.close()


def test_graded_question_is_synced_to_bank(env):
    store, service = env
    pending = PendingQuestion(
        question_id="q1",
        knowledge_point_id="k1",
        question_type="choice",
        prompt="2+2?",
        expected_answer="B",
        explanation="two plus two",
        difficulty="easy",
        options=[{"label": "A", "body": "3"}, {"label": "B", "body": "4"}],  # type: ignore[arg-type]
    )
    service.register_question("p", pending)
    service.grade("p", "q1", "B")
    entries = store.list_bank_entries("p")
    assert len(entries) == 1
    entry = entries[0]
    # knowledge-point link is automatic
    assert entry.knowledge_point_id == "k1"
    assert entry.knowledge_point_name == "fact one"
    assert entry.correct_answer == "B"
    assert entry.user_answer == "B"
    assert entry.explanation == "two plus two"
    assert entry.difficulty == "easy"
    assert entry.tags == []


def test_qualitative_assessment_is_synced_to_bank(env):
    store, service = env
    service.assess("p", "k2", passed=True, evidence="explained in my own words")
    entries = store.list_bank_entries("p")
    assert entries and entries[0].knowledge_point_id == "k2"
    assert entries[0].question_type == "written"
    assert entries[0].is_correct is True


def test_tags_are_manual_and_deduped(env):
    store, service = env
    pending = PendingQuestion(
        question_id="q1", knowledge_point_id="k1", question_type="short", expected_answer="4"
    )
    service.register_question("p", pending)
    service.grade("p", "q1", "4")
    entry_id = store.list_bank_entries("p")[0].entry_id
    service.tag_question(entry_id, ["exam", "hard", "exam"])
    assert store.get_bank_entry(entry_id).tags == ["exam", "hard"]


def test_list_questions_filter_by_tag(env):
    store, service = env
    for i in range(2):
        service.register_question(
            "p",
            PendingQuestion(
                question_id=f"q{i}", knowledge_point_id="k1", question_type="short", expected_answer="4"
            ),
        )
        service.grade("p", f"q{i}", "4")
    first = store.list_bank_entries("p")[0]
    service.tag_question(first.entry_id, ["exam"])
    assert len(service.list_questions("p")) == 2
    assert len(service.list_questions("p", tag="exam")) == 1


def test_api_questions_and_tags(tmp_path):
    store = LearningStore(tmp_path)
    service = LearningService(store)
    service.build(
        "p",
        {"modules": [{"name": "M", "knowledge_points": [{"name": "fact", "type": "memory"}]}]},
    )
    pending = PendingQuestion(
        question_id="q1", knowledge_point_id="k1", question_type="short", expected_answer="4"
    )
    service.register_question("p", pending)
    service.grade("p", "q1", "4")
    app = create_app(store)
    with TestClient(app) as client:
        entries = client.get("/learning/paths/p/questions").json()
        assert len(entries) == 1
        entry_id = entries[0]["entry_id"]
        tagged = client.post(
            f"/learning/questions/{entry_id}/tags", json={"tags": ["exam"]}
        ).json()
        assert tagged["tags"] == ["exam"]
        filtered = client.get("/learning/paths/p/questions", params={"tag": "exam"}).json()
        assert len(filtered) == 1
    store.close()
