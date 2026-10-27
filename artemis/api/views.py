"""Lane C's UI-facing view-models (the API's response/request bodies). Raw paise, enums and ids only: formatting is the
UI's job, so a redesign never touches the server. Bump SCHEMA_VERSION on breaking changes; the OpenAPI document in
contracts/openapi.json is generated from these and the UI's TypeScript types are generated from that."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from artemis.models import CaseState, Tier

SCHEMA_VERSION = 1
Status = Literal["AUTO_CLOSED", "VERIFIED", "PROBABLE", "INSUFFICIENT", "CONFLICTING"]
Decision = Literal["approve", "reject", "request_evidence"]


class _Out(BaseModel):
    """Response models: the server always sends defaulted fields, so the schema (and the UI types) say they are required."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class _View(_Out):
    schema_version: int = SCHEMA_VERSION


# ---------------------------------------------------------------- dashboard
class CaseSummary(_Out):
    case_id: str
    utrs: list[str]
    customer_id: str | None
    customer_name: str | None
    receipt_paise: int
    variance_paise: int | None
    unexplained_paise: int | None
    status: Status | None  # None until the case has been graded or auto-closed
    state: CaseState
    steps: int | None  # agent steps taken (None for auto-closed / not yet investigated)
    duplicate: bool = False


class RupeeSummary(_Out):
    investigated_variance_paise: int  # total apparent variance across investigated cases
    explained_verified_paise: int  # explained by Verified cases
    held_paise: int  # held for evidence or review (Probable, Insufficient, Conflicting)


class CaseList(_View):
    total: int  # all cases, ignoring filters
    counts_by_status: dict[str, int]  # tiles stay put when a filter is applied
    rupees: RupeeSummary
    cases: list[CaseSummary]


# ---------------------------------------------------------------- case detail
class ReceiptView(_Out):
    utr: str
    value_date: str
    amount_paise: int
    payer_name_raw: str
    narration: str
    bank_charges_paise: int
    resolution_score: int | None


class InvoiceView(_Out):
    id: str
    invoice_date: str
    due_date: str
    taxable_paise: int
    gst_paise: int
    gross_paise: int
    status: str


class AllocationView(_Out):
    invoice_id: str
    amount_paise: int


class AdjustmentView(_Out):
    kind: str
    amount_paise: int
    validated: bool
    validated_by_rule: str
    evidence_ids: list[str]


class EvidenceView(_Out):
    id: str
    kind: str
    tier: Tier
    source_table: str
    source_id: str
    excerpt: str
    tool_call_id: str | None
    tool_name: str | None


class FlagSide(_Out):
    ref: str  # an evidence id, or 'table:id' when the grader found it without the agent
    kind: str
    excerpt: str
    amount_paise: int | None  # the value the UI highlights when the two sides differ


class FlagView(_Out):
    code: int
    detail: str
    a: FlagSide
    b: FlagSide


class GradeView(_Out):
    status: Status | None
    flags: list[FlagView]
    duplicate: bool
    recommendation: str | None


class ClosureLine(_Out):
    kind: str
    amount_paise: int
    validated: bool


class VarianceClosure(_Out):
    """Slide 5: invoiced, minus each validated adjustment, equals expected, against received, then unexplained."""
    invoiced_paise: int
    adjustments: list[ClosureLine]
    expected_paise: int
    received_paise: int
    unexplained_paise: int


class ProposedEntry(_Out):
    kind: Literal["allocation", "adjustment"]
    invoice_id: str | None
    account: str | None  # e.g. 'TDS receivable' for a TDS adjustment
    amount_paise: int


class ActionState(_Out):
    allowed: bool
    reason: str | None


class ReviewerActions(_Out):
    reviewer_id: str
    name: str
    role: str
    approve: ActionState
    request_evidence: ActionState
    reject: ActionState


class RunInfo(_Out):
    run_id: str
    model: str
    prompt_version: str
    stop_reason: str | None
    steps: int
    replay: bool


class CaseDetail(_View):
    case_id: str
    state: CaseState
    status: Status | None
    customer_id: str | None
    customer_name: str | None
    receipts: list[ReceiptView]
    invoices: list[InvoiceView]
    allocations: list[AllocationView]
    adjustments: list[AdjustmentView]
    evidence: list[EvidenceView]
    grade: GradeView
    closure: VarianceClosure | None
    proposed_entries: list[ProposedEntry]
    narrative: str | None
    narrative_source: Literal["llm", "template"] | None
    run: RunInfo | None
    actions: list[ReviewerActions]


# ---------------------------------------------------------------- evidence graph (topology only; the browser lays it out)
class GraphNode(_Out):
    id: str
    kind: Literal["receipt", "invoice", "adjustment", "evidence", "rule"]
    label: str
    tier: Tier | None = None  # primary => solid border, supporting => dashed
    amount_paise: int | None = None
    validated: bool | None = None


class GraphEdge(_Out):
    id: str
    source: str
    target: str
    kind: Literal["allocates", "adjusts", "supports", "contradicts", "rule"]
    label: str | None = None
    amount_paise: int | None = None


class EvidenceGraph(_View):
    case_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ---------------------------------------------------------------- review
class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Decision
    comment: str = Field(default="", max_length=1000)


class AppliedInvoice(_Out):
    invoice_id: str
    status: str


class ReviewResult(_View):
    case_id: str
    decision: Decision
    state: CaseState
    applied: list[AppliedInvoice]
    audit_seq: int  # seq of the REVIEW_DECIDED event, so the UI can show it without a reload


class ReviewerView(_Out):
    id: str
    name: str
    role: str
    approval_limit_paise: int | None


# ---------------------------------------------------------------- audit
class AuditEventView(_Out):
    seq: int
    case_id: str | None
    event_type: str
    actor: str
    payload: dict
    hash: str
    prev_hash: str
    created_at: str


class AuditList(_View):
    events: list[AuditEventView]


class VerifyResult(_View):
    ok: bool
    first_broken_seq: int | None
    checked: int
    checkpoints: int
    reason: str | None


# ---------------------------------------------------------------- batch
class BatchRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["demo", "replay", "live"] = "demo"


class ModeInfo(_Out):
    mode: Literal["demo", "replay", "live"]
    label: str
    available: bool
    reason: str | None  # why it is unavailable (e.g. no recording yet, no API key)


class Modes(_View):
    modes: list[ModeInfo]


class BatchStarted(_View):
    batch_id: str
    mode: Literal["demo", "replay", "live"]


class ResetResult(_View):
    cases: int
    auto_closed: int


class TamperResult(_View):
    """What the demo tamper changed: one audit event, edited as the database owner. Verify chain then fails at `seq`."""
    seq: int
    field: str
    before: int | str | None
    after: int | str

