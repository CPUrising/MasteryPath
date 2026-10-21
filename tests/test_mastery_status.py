"""The tutor-facing state snapshot (mastery_status)."""

from __future__ import annotations

import json

import pytest

from masterypath.capabilities.mastery import mode
from masterypath.capabilities.mastery.tools import (
    MasteryBuildTool,
    MasteryStatusTool,
    ToolContext,
)
from masterypath.learning.models import PendingQuestion
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(tmp_path)
    service = LearningService(store)
    yield store, service
    store.close()


def _ctx(service, mode_value=mode.OUTLINE):
    return ToolContext(service=service, path_id="p", session_mode=mode_value)


def _build(service):
    return MasteryBuildTool().execute(
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
        _ctx(service),
    )


def test_empty_goal_is_not_reported_as_complete(env):
    _, service = env
    service.create_path("p", goal="learn X", name="X")

    payload = json.loads(MasteryStatusTool().execute({}, _ctx(service)).content)

    assert payload["status"] == "empty"
    assert payload["goal"] == "learn X"
    assert payload["map"] == {}
    assert payload["next"] == {}
    assert "mastery_build" in payload["message"]


def test_active_path_exposes_ids_next_and_mode(env):
    _, service = env
    service.create_path("p", goal="learn X", name="X")
    _build(service)

    payload = json.loads(
        MasteryStatusTool().execute({}, _ctx(service, mode.STUDY)).content
    )

    assert payload["status"] == "active"
    assert set(payload["map"]) == {"k1", "k2"}
    assert payload["next"]["knowledge_point_id"] == "k1"
    assert payload["mode"] == "study"
    assert payload["name"] == "X"


def test_build_returns_the_map_so_the_tutor_sees_ids(env):
    _, service = env
    service.create_path("p", goal="learn X", name="X")

    result = _build(service)

    assert result.ok is True
    assert '"k1"' in result.content
    assert result.metadata["map"]["k1"]["name"] == "fact one"
    assert result.metadata["next"]["knowledge_point_id"] == "k1"


def test_pending_question_is_public(env):
    _, service = env
    service.create_path("p", goal="learn X", name="X")
    _build(service)
    service.register_question(
        "p",
        PendingQuestion(
            question_id="q1",
            knowledge_point_id="k1",
            question_type="short",
            prompt="2+2?",
            expected_answer="4",
            explanation="four",
        ),
    )

    payload = json.loads(MasteryStatusTool().execute({}, _ctx(service)).content)

    pending = payload["pending_question"]
    assert pending["question_id"] == "q1"
    assert pending["prompt"] == "2+2?"
    assert "expected_answer" not in pending
    assert "explanation" not in pending
    assert payload["next"]["action"] == "answer_pending"
