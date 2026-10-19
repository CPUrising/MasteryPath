"""TC-N1..N6 — outline generation quality (ADR-018 / spec 09)."""

from __future__ import annotations

import pytest

from masterypath.learning.models import TopicSource
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def service(tmp_path):
    store = LearningStore(tmp_path)
    yield LearningService(store)
    store.close()


def test_tc_n1_build_returns_coverage(service):
    service.build("p", {"modules": [{"name": "M", "knowledge_points": [{"name": "obj", "type": "memory"}]}]})
    coverage = service.get_coverage("p")
    assert coverage["documents"] == 0 and coverage["reported"] is False
    assert coverage["acyclic"] is True


def test_tc_n2_unused_source_is_missing(service):
    service.attach_sources("p", [TopicSource(id="s1", label="a.md"), TopicSource(id="s2", label="b.md")])
    service.build(
        "p",
        {
            "modules": [
                {
                    "name": "M",
                    "knowledge_points": [{"name": "obj", "type": "concept", "sources": ["a.md"]}],
                }
            ]
        },
    )
    coverage = service.get_coverage("p")
    assert coverage["documents"] == 2 and coverage["covered"] == 1
    assert any(gap["label"] == "s2" for gap in coverage["missing"])


def test_tc_n3_unreported_does_not_expand_missing(service):
    service.attach_sources("p", [TopicSource(id="s1", label="a.md")])
    service.build("p", {"modules": [{"name": "M", "knowledge_points": [{"name": "obj", "type": "memory"}]}]})
    coverage = service.get_coverage("p")
    assert coverage["reported"] is False
    assert coverage["missing"] == []


def test_tc_n4_cycle_detected(service):
    service.build(
        "p",
        {
            "modules": [
                {
                    "name": "M",
                    "knowledge_points": [
                        {"name": "alpha", "type": "memory", "prerequisites": ["beta"]},
                        {"name": "beta", "type": "memory", "prerequisites": ["alpha"]},
                    ],
                }
            ]
        },
    )
    assert service.get_coverage("p")["acyclic"] is False


def test_tc_n5_eval_passes_when_covered(service):
    service.attach_sources("p", [TopicSource(id="s1", label="a.md")])
    service.build(
        "p",
        {
            "modules": [
                {
                    "name": "M",
                    "knowledge_points": [{"name": "obj", "type": "concept", "sources": ["a.md"]}],
                }
            ]
        },
    )
    report = service.eval_outline("p")
    assert report["coverage_ratio"] == 1.0
    assert report["passed"] is True


def test_tc_n6_deterministic(service):
    service.attach_sources("p", [TopicSource(id="s1", label="a.md")])
    service.build(
        "p",
        {
            "modules": [
                {
                    "name": "M",
                    "knowledge_points": [{"name": "obj", "type": "concept", "sources": ["a.md"]}],
                }
            ]
        },
    )
    assert service.eval_outline("p") == service.eval_outline("p")


def test_eval_cli_passes_on_matching_case(tmp_path):
    import json

    from masterypath.eval.__main__ import main

    cases = tmp_path / "cases.jsonl"
    modules = [{"name": "M", "knowledge_points": [{"name": "理解线程", "type": "concept"}]}]
    cases.write_text(
        json.dumps({"id": "c1", "reference_modules": modules, "generated_modules": modules}) + "\n",
        encoding="utf-8",
    )
    assert main(["outline", "--cases", str(cases)]) == 0


def test_eval_cli_fails_on_cycle(tmp_path):
    import json

    from masterypath.eval.__main__ import main

    modules = [
        {
            "name": "M",
            "knowledge_points": [
                {"name": "alpha", "prerequisites": ["beta"]},
                {"name": "beta", "prerequisites": ["alpha"]},
            ],
        }
    ]
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        json.dumps({"id": "c1", "reference_modules": modules}) + "\n", encoding="utf-8"
    )
    assert main(["outline", "--cases", str(cases)]) == 1
