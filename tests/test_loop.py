"""Agent loop + mode gating at call time + fake client (spec 05 §三, 02)."""

from __future__ import annotations

import pytest

from masterypath.agents.llm import FakeLLMClient, LLMResponse, ToolCall
from masterypath.agents.loop import AgentLoop
from masterypath.capabilities.mastery import mode
from masterypath.capabilities.mastery.tools import TOOLS, ToolContext
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(tmp_path)
    yield ToolContext(
        service=LearningService(store), path_id="p", session_mode=mode.OUTLINE
    )
    store.close()


def _build_call():
    return ToolCall(
        name="mastery_build",
        arguments={
            "modules": [
                {
                    "name": "Basics",
                    "knowledge_points": [{"name": "objective", "type": "concept"}],
                }
            ]
        },
        id="call-build",
    )


def test_loop_builds_outline_then_finishes(ctx):
    client = FakeLLMClient(
        [LLMResponse(tool_calls=[_build_call()]), LLMResponse(text="Outline ready.")]
    )
    events = AgentLoop(TOOLS).run(client, [{"role": "user", "content": "teach me X"}], ctx)
    types = [event.type for event in events]
    assert types == ["tool_call", "tool_result", "text_delta", "turn_end"]
    tool_result = events[1]
    assert tool_result.data["ok"] is True
    assert ctx.service.get_state("p")["map"]  # map exists
    # system prompt framed the mode
    assert "Current mode: outline" in client.calls[0][0]["content"]


def test_loop_refuses_tool_in_wrong_mode(ctx):
    ctx.session_mode = mode.STUDY  # build belongs to outline only
    client = FakeLLMClient(
        [LLMResponse(tool_calls=[_build_call()]), LLMResponse(text="ok")]
    )
    events = AgentLoop(TOOLS).run(client, [{"role": "user", "content": "go"}], ctx)
    tool_result = next(event for event in events if event.type == "tool_result")
    assert tool_result.data["ok"] is False
    assert "mastery_mode" in tool_result.data["content"]
    assert ctx.service.get_state("p")["status"] == "missing"  # no map written


def test_loop_unknown_tool(ctx):
    client = FakeLLMClient(
        [LLMResponse(tool_calls=[ToolCall(name="nope", arguments={})]), LLMResponse(text="done")]
    )
    events = AgentLoop(TOOLS).run(client, [{"role": "user", "content": "x"}], ctx)
    tool_result = next(event for event in events if event.type == "tool_result")
    assert tool_result.data["ok"] is False


def test_loop_stops_at_max_rounds(ctx):
    looping = LLMResponse(tool_calls=[ToolCall(name="mastery_revise", arguments={"ops": []})])
    client = FakeLLMClient([looping, looping, looping, looping, looping, looping, looping])
    events = AgentLoop(TOOLS, max_rounds=2).run(client, [{"role": "user", "content": "x"}], ctx)
    assert events[-1].data["reason"] == "max_rounds"


def test_loop_sends_tool_definitions(ctx):
    client = FakeLLMClient([LLMResponse(text="hello")])
    AgentLoop(TOOLS).run(client, [{"role": "user", "content": "x"}], ctx)
    definitions = client.tools_seen[0]
    names = {item["function"]["name"] for item in definitions}
    assert names == set(TOOLS)
    assert all("parameters" in item["function"] for item in definitions)


def test_loop_writes_openai_tool_history(ctx):
    client = FakeLLMClient(
        [LLMResponse(tool_calls=[_build_call()]), LLMResponse(text="done")]
    )
    AgentLoop(TOOLS).run(client, [{"role": "user", "content": "x"}], ctx)
    second_round = client.calls[1]
    assistant = [m for m in second_round if m["role"] == "assistant" and m.get("tool_calls")]
    assert assistant, "assistant tool_calls message missing"
    call_id = assistant[0]["tool_calls"][0]["id"]
    tool_messages = [m for m in second_round if m["role"] == "tool"]
    assert tool_messages and tool_messages[0]["tool_call_id"] == call_id


def test_loop_degrades_on_bad_arguments(ctx):
    bad = ToolCall(name="mastery_build", arguments={}, id="c1", parse_error=True)
    client = FakeLLMClient([LLMResponse(tool_calls=[bad]), LLMResponse(text="ok")])
    events = AgentLoop(TOOLS).run(client, [{"role": "user", "content": "x"}], ctx)
    tool_result = next(event for event in events if event.type == "tool_result")
    assert tool_result.data["ok"] is False
    assert "invalid tool arguments" in tool_result.data["content"]
    assert ctx.service.get_state("p")["status"] == "missing"
