"""Domain model for MasteryPath (spec 01-domain-model.md).

Pydantic v2 entities with ``extra="ignore"`` so historical JSON still loads.
No I/O, no LLM. Invariants are enforced where structural (INV-16, INV-26).
"""

from __future__ import annotations

from enum import Enum
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_KNOWLEDGE_TYPE_LEGACY: dict[str, str] = {
    "记忆型": "memory",
    "概念型": "concept",
    "程序型": "procedure",
    "设计型": "design",
}

_ERROR_TYPE_LEGACY: dict[str, str] = {
    "知识结构性": "structural",
    "理解偏差型": "deviation",
    "应用错误": "application",
    "元认知型": "metacognitive",
}


class KnowledgeType(str, Enum):
    MEMORY = "memory"
    CONCEPT = "concept"
    PROCEDURE = "procedure"
    DESIGN = "design"

    @classmethod
    def _missing_(cls, value: object) -> "KnowledgeType | None":
        mapped = _KNOWLEDGE_TYPE_LEGACY.get(str(value))
        return cls(mapped) if mapped else None


class ErrorType(str, Enum):
    STRUCTURAL = "structural"
    DEVIATION = "deviation"
    APPLICATION = "application"
    METACOGNITIVE = "metacognitive"

    @classmethod
    def _missing_(cls, value: object) -> "ErrorType | None":
        mapped = _ERROR_TYPE_LEGACY.get(str(value))
        return cls(mapped) if mapped else None


class InteractionStatus(str, Enum):
    REGISTERED = "registered"
    AWAITING_INPUT = "awaiting_input"
    ANSWERED = "answered"
    GRADED = "graded"
    ABANDONED = "abandoned"


class AssessmentType(str, Enum):
    QUIZ = "quiz"
    QUALITATIVE = "qualitative"
    REVIEW = "review"


class AssessmentResult(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"


class GapKind(str, Enum):
    GOAL_GAP = "goal_gap"
    SOURCE_OMISSION = "source_omission"


class GapResolution(str, Enum):
    ACCEPTED = "accepted"
    REGENERATED = "regenerated"


class KnowledgePoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    type: KnowledgeType
    module_id: str
    prerequisite_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    # Additional required evidence tags (INV-28). Empty => no extra condition.
    required_evidence: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_min_length(cls, value: str) -> str:
        if len(value.strip()) < 2:
            raise ValueError("knowledge point name must be at least 2 characters")
        return value

    @property
    def grounding(self) -> Literal["grounded", "ungrounded"]:
        return "grounded" if self.source_ids else "ungrounded"


class LearningModule(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    order: int
    objective: str = ""
    # Display-only target; never gates advancement (INV-18).
    display_target: float = 0.7
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)


class QuizAttempt(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_id: str
    knowledge_point_id: str
    module_id: str = ""
    is_correct: bool
    user_answer: Any = None
    error_type: ErrorType | None = None
    independent: bool = True
    mastery_estimate: float = 0.0
    voided: bool = False
    void_reason: str = ""
    timestamp: float = Field(default_factory=time.time)


class LearningEvidence(BaseModel):
    """Append-only durable review/assessment event (INV-12)."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str = ""
    question_id: str = ""
    knowledge_point_id: str
    assessment_type: AssessmentType = AssessmentType.QUIZ
    result: AssessmentResult = AssessmentResult.INCORRECT
    quality: float | None = None
    hints_used: int = 0
    attempt_count: int = 1
    session_id: str = ""
    turn_id: str = ""
    source: str = "mastery_path"
    timestamp: float = Field(default_factory=time.time)


class RepetitionState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    interval_index: int = 0
    consecutive_correct: int = 0
    consecutive_wrong: int = 0
    next_review_at: float
    ease_factor: float = 2.5
    last_review_at: float | None = None
    last_scheduled_at: float | None = None
    scheduled_after_failure: bool = False
    review_count: int = 0
    lapse_count: int = 0
    provenance: Literal["system", "learner"] = "system"
    desired_retention: float = 0.9
    # FSRS fields: display-only under SM-2 (INV-31).
    difficulty: float = 0.3
    stability: float = 0.0
    retrievability: float = 1.0


class ReviewTask(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    knowledge_point_id: str
    knowledge_type: KnowledgeType
    due_at: float
    priority: int = 0
    state: RepetitionState
    forgetting_risk: float = 0.0
    reason: str = ""
    evidence_source: str = ""
    evidence_id: str = ""


class PendingOption(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str
    body: str


class PendingQuestion(BaseModel):
    """A posed question; answer + explanation stay server-side (INV-07)."""

    model_config = ConfigDict(extra="ignore")

    question_id: str
    knowledge_point_id: str
    module_id: str = ""
    prompt: str = ""
    question_type: Literal["choice", "short", "open"] = "short"
    expected_answer: str = ""
    options: list[PendingOption] = Field(default_factory=list)
    explanation: str = ""
    difficulty: str = ""
    accepted_answers: list[str] = Field(default_factory=list)
    # Open-question keywords are fixed at registration (INV-35) so grading is
    # deterministic and never calls an LLM.
    required_keywords: list[str] = Field(default_factory=list)
    optional_keywords: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    @property
    def choice_map(self) -> dict[str, str]:
        return {option.label: option.body for option in self.options}

    @field_validator("options", mode="before")
    @classmethod
    def _read_legacy_option_strings(cls, value: Any) -> Any:
        """Read the plain-string option rows written before options were split."""
        if not isinstance(value, list) or not value:
            return value
        if not all(isinstance(entry, str) for entry in value):
            return value
        from masterypath.learning.pending import parse_options

        return [
            {"label": label, "body": body}
            for label, body in parse_options(value).items()
        ]


class LearnerMasteryOverride(BaseModel):
    model_config = ConfigDict(extra="ignore")

    knowledge_point_id: str
    note: str = ""
    created_at: float = Field(default_factory=time.time)


class DeferredObjective(BaseModel):
    model_config = ConfigDict(extra="ignore")

    knowledge_point_id: str
    note: str = ""
    created_at: float = Field(default_factory=time.time)


class SourceGap(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    kind: GapKind
    ref: str = ""
    reason: str = ""
    candidate_source_ids: list[str] = Field(default_factory=list)
    resolution: GapResolution | None = None
    created_at: float = Field(default_factory=time.time)


class MasteryInteraction(BaseModel):
    """A persisted question/answer transaction (key = interaction_id)."""

    model_config = ConfigDict(extra="ignore")

    interaction_id: str
    path_id: str
    question: PendingQuestion
    status: InteractionStatus = InteractionStatus.REGISTERED
    session_id: str = ""
    turn_id: str = ""
    user_answer: str = ""
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    @property
    def is_terminal(self) -> bool:
        return self.status in (InteractionStatus.GRADED, InteractionStatus.ABANDONED)

    @property
    def is_open(self) -> bool:
        return self.status in (
            InteractionStatus.REGISTERED,
            InteractionStatus.AWAITING_INPUT,
            InteractionStatus.ANSWERED,
        )


class MasteryEvent(BaseModel):
    """Append-only domain event (spec 05-api-contract.md §四)."""

    model_config = ConfigDict(extra="ignore")

    id: int = 0
    path_id: str
    revision: int
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    session_id: str = ""
    turn_id: str = ""
    created_at: float = Field(default_factory=time.time)


class QuestionBankEntry(BaseModel):
    """One graded attempt stored for later review (spec 06/05).

    The knowledge-point link is automatic; ``tags`` are manual (MVP).
    """

    model_config = ConfigDict(extra="ignore")

    entry_id: str
    path_id: str
    knowledge_point_id: str
    knowledge_point_name: str = ""
    question_id: str = ""
    question: str = ""
    question_type: str = "short"
    options: list[dict[str, Any]] = Field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = ""
    user_answer: str = ""
    is_correct: bool = False
    result: str = "incorrect"
    source: str = "mastery_path"
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class TopicMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path_id: str
    goal: str = ""
    description: str = ""
    emoji: str = "🧭"
    status: Literal["active", "archived"] = "active"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class TopicSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    kind: Literal["goal", "book", "notebook", "knowledge_base", "file"] = "file"
    source_id: str = ""
    label: str = ""
    excerpt: str = ""
    position: int = 0
    available: bool = True


class LearningProgress(BaseModel):
    """The path aggregate root (spec 01)."""

    model_config = ConfigDict(extra="ignore")

    path_id: str
    name: str = ""
    goal: str = ""
    modules: list[LearningModule] = Field(default_factory=list)
    current_module_id: str = ""
    current_kp_index: int = 0
    knowledge_types: dict[str, KnowledgeType] = Field(default_factory=dict)
    mastery_levels: dict[str, float] = Field(default_factory=dict)
    qualitative_mastery: dict[str, bool] = Field(default_factory=dict)
    quiz_attempts: list[QuizAttempt] = Field(default_factory=list)
    learning_evidence: list[LearningEvidence] = Field(default_factory=list)
    repetition_states: dict[str, RepetitionState] = Field(default_factory=dict)
    review_queue: list[ReviewTask] = Field(default_factory=list)
    learner_mastery_overrides: dict[str, LearnerMasteryOverride] = Field(default_factory=dict)
    deferred_objectives: dict[str, DeferredObjective] = Field(default_factory=dict)
    explained_objectives: dict[str, dict[str, Any]] = Field(default_factory=dict)
    source_gaps: list[SourceGap] = Field(default_factory=list)
    pending_question: PendingQuestion | None = None
    desired_retention: float = Field(default=0.9, ge=0.7, le=0.99, allow_inf_nan=False)
    version: int = 0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    def find_knowledge_point(self, kp_id: str):
        for module in self.modules:
            for kp in module.knowledge_points:
                if kp.id == kp_id:
                    return kp, module
        return None, None


__all__ = [
    "KnowledgeType",
    "ErrorType",
    "InteractionStatus",
    "AssessmentType",
    "AssessmentResult",
    "GapKind",
    "GapResolution",
    "KnowledgePoint",
    "LearningModule",
    "QuizAttempt",
    "LearningEvidence",
    "RepetitionState",
    "ReviewTask",
    "PendingOption",
    "PendingQuestion",
    "LearnerMasteryOverride",
    "DeferredObjective",
    "SourceGap",
    "MasteryInteraction",
    "MasteryEvent",
    "QuestionBankEntry",
    "TopicMetadata",
    "TopicSource",
    "LearningProgress",
]
