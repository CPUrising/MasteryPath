"""mastery_mode: admission, same-turn rebinding and persistence."""

from __future__ import annotations

import pytest

from masterypath.agents.llm import FakeLLMClient, LLMResponse, ToolCall
from masterypath.agents.loop import AgentLoop
from masterypath.capabilities.mastery import mode
from masterypath.capabilities.mastery.tools import (
    TOOLS,
    MasteryBuildTool,
    MasteryModeTool,
    ToolContext,
)
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(tmp_path)
    service = LearningService(store)
    service.create_path("p", goal="learn X", name="X")
    yield store, service
    store.close()


def _ctx(service, *, mode_value=mode.OUTLINE, session_id=""):
    return ToolContext(
        service=service,
        path_id="p",
        session_mode=mode_value,
        session_id=session_id,
    )


def _build(service):
    MasteryBuildTool().execute(
        {
            "modules": [
                {
                    "name": "M",
                    "knowledge_points": [{"name": "fact one", "type": "memory"}],
                }
            ]
        },
        _ctx(service),
    )


def test_rejects_an_unknown_mode(env):
    _, service = env

    result = MasteryModeTool().execute({"mode": "banana"}, _ctx(service))

    assert result.ok is False
    assert "outline" in result.content and "study" in result.content


def test_study_without_outline_is_refused(env):
    _, service = env
    ctx = _ctx(service)

    result = MasteryModeTool().execute({"mode": "study"}, ctx)

    assert result.ok is False
    assert "no outline" in result.content.lower()
    assert ctx.session_mode == mode.OUTLINE


def test_switch_rebinds_the_turn_and_persists(env):
    store, service = env
    _build(service)
    service.ensure_session("p", "s1", mode=mode.OUTLINE)
    ctx = _ctx(service, session_id="s1")

    result = MasteryModeTool().execute(
        {"mode": "study", "reason": "start learning"}, ctx
    )

    assert result.ok is True
    assert ctx.session_mode == mode.STUDY
    assert ctx.mode_changed is True
    assert store.get_session("s1")["mode"] == mode.STUDY
    assert result.metadata["mode"] == mode.STUDY
    assert "teaching" in result.content


def test_mode_switch_and_quiz_in_one_round_use_the_new_mode(env):
    store, service = env
    _build(service)
    service.ensure_session("p", "s1", mode=mode.OUTLINE)
    ctx = _ctx(service, session_id="s1")
    client = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        name="mastery_mode",
                        arguments={"mode": "study", "reason": "begin"},
                        id="c1",
                    ),
                    ToolCall(
                        name="mastery_quiz",
                        arguments={
                            "knowledge_point_id": "k1",
                            "question": "2+2?",
                            "expected_answer": "4",
                        },
                        id="c2",
                    ),
                ]
            )
        ]
    )

    events = AgentLoop(TOOLS).run(
        client, [{"role": "user", "content": "let us start"}], ctx
    )

    results = [event for event in events if event.type == "tool_result"]
    assert [result.data["ok"] for result in results] == [True, True]
    assert results[0].data["metadata"]["mode"] == mode.STUDY
    assert ctx.session_mode == mode.STUDY
    assert store.get_session("s1")["mode"] == mode.STUDY
