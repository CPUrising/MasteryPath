"""TC-A1..A6 — model & validation (spec 03 §A)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from masterypath.learning.models import (
    KnowledgePoint,
    KnowledgeType,
    LearningModule,
    LearningProgress,
    PendingQuestion,
)


def test_tc_a1_name_too_short_rejected():
    with pytest.raises(ValidationError):
        KnowledgePoint(id="k", name="a", type=KnowledgeType.MEMORY, module_id="m")


def test_tc_a2_unknown_type_rejected():
    with pytest.raises(ValidationError):
        KnowledgePoint(id="k", name="ab", type="foo", module_id="m")  # type: ignore[arg-type]


def test_tc_a3_legacy_type_mapping():
    kp = KnowledgePoint(id="k", name="ab", type="概念型", module_id="m")  # type: ignore[arg-type]
    assert kp.type is KnowledgeType.CONCEPT


def test_tc_a4_unknown_fields_ignored():
    kp = KnowledgePoint(
        id="k", name="ab", type="concept", module_id="m", whatever=123  # type: ignore[call-arg]
    )
    assert kp.name == "ab"
    assert kp.type is KnowledgeType.CONCEPT


def test_tc_a5_legacy_option_strings_parsed():
    q = PendingQuestion(
        question_id="q", knowledge_point_id="k", options=["A: x", "B: y"]  # type: ignore[arg-type]
    )
    assert q.choice_map == {"A": "x", "B": "y"}


def test_tc_a6_roundtrip_equality():
    p = LearningProgress(
        path_id="p", modules=[LearningModule(id="m", name="M", order=0)]
    )
    assert LearningProgress.model_validate_json(p.model_dump_json()) == p
