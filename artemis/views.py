"""UI-facing view-models. Raw data only (paise, enums, ids; no formatted strings) so any UI redesign
is Lane C's job alone. Bump SCHEMA_VERSION on breaking changes; schemas export to contracts/."""
from __future__ import annotations

from pydantic import BaseModel, Field

from artemis.models import AgentRun, EvidenceStatus, Hypothesis, StopReason, ToolCall

SCHEMA_VERSION = 1


class TraceStep(BaseModel):
    step: int
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)


class TraceView(BaseModel):  # GET /cases/{id}/trace
    schema_version: int = SCHEMA_VERSION
    case_id: str
    run: AgentRun
    replay: bool = False
    tool_path: list[str]
    steps: list[TraceStep]


class NarrativeView(BaseModel):
    schema_version: int = SCHEMA_VERSION
    case_id: str
    text: str
    source: str  # "llm" | "template"  (UI shows the template badge)


class BatchStatus(BaseModel):  # GET /batch/{id}
    schema_version: int = SCHEMA_VERSION
    batch_id: str
    replay: bool = False
    total: int = 0
    done: int = 0
    running: bool = True
    counts_by_status: dict[str, int] = Field(default_factory=dict)
    counts_by_state: dict[str, int] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    run_ids: dict[str, str] = Field(default_factory=dict)  # case_id -> agent run id


class MetricsReport(BaseModel):  # GET /metrics
    schema_version: int = SCHEMA_VERSION
    runs: int
    cases: int
    verified_precision: float | None
    evidence_coverage: float | None
    abstention_accuracy: float | None
    autonomous_completion: float | None
    status_accuracy: float | None
    allocation_accuracy: float | None
    confusion: dict[str, dict[str, int]]  # truth -> graded -> count
    tool_path_diversity: int
    mean_steps: float
    mean_tokens: float
    mean_seconds: float
    estimated_cost_paise: int | None = None
    false_clears: list[str] = Field(default_factory=list)
    red_team_applied: list[str] = Field(default_factory=list)
    spread: dict[str, list[float]] = Field(default_factory=dict)  # metric -> value per run


__all__ = ["TraceView", "TraceStep", "NarrativeView", "BatchStatus", "MetricsReport",
           "SCHEMA_VERSION", "EvidenceStatus", "StopReason"]
