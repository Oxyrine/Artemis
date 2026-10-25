from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

from artemis.models import AllocationResult, CoreResult, Evidence, EvidenceRef


@dataclass
class RunState:
    allocation: AllocationResult | None = None  # last propose_allocation result
    evidence_requested: bool = False
    finished: bool = False
    summary: str = ""


@dataclass
class ToolContext:
    deps: Any  # artemis.wiring.Deps
    llm: Any  # LLMClient (parse_remittance is the only tool that uses it)
    case_id: str
    run_id: str
    step: int = 0
    call_id: str = ""
    state: RunState = field(default_factory=RunState)
    tokens_in: int = 0
    tokens_out: int = 0

    def save_refs(self, refs: list[EvidenceRef]) -> list[str]:
        """Persist what a tool found as Evidence rows; returns their ids for the agent to cite."""
        ids = []
        for r in refs:
            ev = Evidence(id=self.deps.store.next_id("EV"), case_id=self.case_id,
                          retrieved_by_tool_call_id=self.call_id, **r.model_dump())
            self.deps.store.add_evidence(ev)
            ids.append(ev.id)
        return ids

    def out(self, res: CoreResult) -> dict:
        return {**res.data, "evidence_ids": self.save_refs(res.refs)}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input: type[BaseModel]
    fn: Callable[[ToolContext, Any], dict]
