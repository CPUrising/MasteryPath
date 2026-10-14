"""M4 — qualitative assessment (mastery_assess) for CONCEPT / DESIGN (INV-05)."""

from __future__ import annotations

import pytest

from masterypath.capabilities.mastery import mode
from masterypath.capabilities.mastery.tools import MasteryAssessTool, ToolContext
from masterypath.learning.models import AssessmentType
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore, PreconditionError


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
                        {"name": "deep idea", "type": "concept"},
                        {"name": "fact", "type": "memory"},
                    ],
                }
            ]
        },
    )
    yield store, service
    store.close()


def _ctx(service, mode_value=mode.STUDY):
    return ToolContext(service=service, path_id="p", session_mode=mode_value)


def test_qualitative_pass_clears_gate(env):
    store, service = env
    result = MasteryAssessTool().execute(
        {"knowledge_point_id": "k1", "passed": True, "evidence": "explained in own words"},
        _ctx(service),
    )
    assert result.ok and result.metadata["gate_cleared"] is True
    assert result.metadata["source"] == "system"
    # evidence is qualitative
    evidence = store.load("p").learning_evidence
    assert evidence and evidence[-1].assessment_type is AssessmentType.QUALITATIVE
    # frontier advances past the concept objective
    assert service.get_state("p")["next"]["knowledge_point_id"] != "k1"


def test_qualitative_fail_does_not_open_gate(env):
    _, service = env
    result = MasteryAssessTool().execute(
        {"knowledge_point_id": "k1", "passed": False}, _ctx(service)
    )
    assert result.ok
    assert result.metadata["gate_cleared"] is False
    assert service.get_state("p")["next"]["knowledge_point_id"] == "k1"


def test_assess_refuses_quantitative_objective(env):
    _, service = env
    with pytest.raises(PreconditionError):
        service.assess("p", "k2", passed=True)  # k2 is memory


def test_review_refuses_unmastered_assess(env):
    _, service = env
    result = MasteryAssessTool().execute(
        {"knowledge_point_id": "k1", "passed": True},
        _ctx(service, mode.REVIEW),
    )
    assert not result.ok


def test_multiple_assessments_allowed_and_evidence_accumulates(env):
    store, service = env
    service.assess("p", "k1", passed=False)
    service.assess("p", "k1", passed=True, evidence="now correct")
    evidence = [e for e in store.load("p").learning_evidence if e.knowledge_point_id == "k1"]
    assert len(evidence) == 2
    assert store.load("p").qualitative_mastery["k1"] is True
