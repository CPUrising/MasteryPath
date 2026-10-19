"""TC-M1..M6 — capture-and-defer, coverage, behavior budget (ADR-017/019)."""

from __future__ import annotations

import pytest

from masterypath.agents.llm import FakeLLMClient, LLMResponse, ToolCall
from masterypath.agents.loop import AgentLoop
from masterypath.capabilities.mastery import mode
from masterypath.capabilities.mastery.tools import (
    MasteryProposeObjectiveTool,
    MasteryReviseTool,
    TOOLS,
    ToolContext,
)
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(tmp_path)
    service = LearningService(store)
    service.build(
        "p", {"modules": [{"name": "M", "knowledge_points": [{"name": "fact one", "type": "memory"}]}]}
    )
    yield store, service
    store.close()


def _ctx(service, mode_value=mode.STUDY):
    return ToolContext(service=service, path_id="p", session_mode=mode_value)


def test_tc_m1_propose_does_not_change_map(env):
    _, service = env
    result = MasteryProposeObjectiveTool().execute(
        {"name": "new idea", "type": "concept", "reason": "discovered while studying"},
        _ctx(service),
    )
    assert result.ok
    state = service.get_state("p")
    assert len(state["proposals"]) == 1 and state["proposals"][0]["status"] == "pending"
    # map and frontier unchanged
    assert state["counts"]["total"] == 1
    assert state["next"]["knowledge_point_id"] == "k1"


def test_tc_m2_revise_refused_in_study(env):
    _, service = env
    result = MasteryReviseTool().execute(
        {"ops": [{"op": "add_kp", "module_id": "m1", "name": "x y", "type": "memory"}]},
        _ctx(service),
    )
    assert not result.ok


def test_tc_m3_accept_proposal_adds_kp(env):
    _, service = env
    proposal = service.propose_objective("p", name="extra idea", kp_type="concept")
    assert service.get_state("p")["counts"]["total"] == 1
    service.resolve_proposal("p", proposal["proposal_id"], "accept")
    state = service.get_state("p")
    assert state["counts"]["total"] == 2
    assert state["proposals"][0]["status"] == "accepted"


def test_tc_m4_build_reports_coverage(env):
    _, service = env
    coverage = service.get_coverage("p")
    assert coverage is not None
    assert {"documents", "covered", "missing", "reported", "grounding_ratio", "acyclic"} <= set(coverage)


def test_tc_m5_eval_flags_low_coverage(env):
    from masterypath.learning.models import TopicSource

    _, service = env
    service.attach_sources(
        "p", [TopicSource(id="s1", label="a.md"), TopicSource(id="s2", label="b.md")]
    )
    # objective cites no source -> nothing covered
    service.revise("p", [{"op": "add_kp", "module_id": "m1", "name": "uncovered", "type": "memory"}])
    report = service.eval_outline("p")
    assert report["documents"] == 2 and report["covered"] == 0
    assert report["passed"] is False


def test_tc_m6_turn_budget(env):
    _, service = env
    calls = [
        ToolCall("mastery_note_explained", {"knowledge_point_id": "k1", "summary": "x"})
        for _ in range(7)
    ]
    client = FakeLLMClient([LLMResponse(tool_calls=calls)])
    events = AgentLoop(TOOLS).run(client, [{"role": "user", "content": "go"}], _ctx(service))
    assert events[-1].type == "turn_end"
    assert events[-1].data["reason"] == "budget"
