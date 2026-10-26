from pydantic import BaseModel

from artemis.models import AdjustmentProposal, AllocationLine, CoreError
from artemis.tools.base import Tool


class Input(BaseModel):
    utrs: list[str]
    allocations: list[AllocationLine]
    adjustments: list[AdjustmentProposal] = []


def _run(ctx, i: Input) -> dict:
    for a in i.adjustments:  # only rounding can be negative; a negated TDS/credit-note/charge is a model slip
        if a.amount_paise < 0 and a.kind != "rounding":
            raise CoreError("invalid_input", f"{a.kind} amount_paise must be positive (got {a.amount_paise}); "
                            "copy the tool's amount exactly, do not negate it")
    known = {e.id for e in ctx.deps.store.evidence(ctx.case_id)}
    bad = sorted({x for a in i.adjustments for x in a.evidence_ids} - known)
    if bad:
        raise CoreError("not_found", f"unknown evidence ids {bad}; cite only ids returned by tools")
    res = ctx.deps.core.propose_allocation(ctx.case_id, i.utrs, [a.model_dump(mode="json") for a in i.allocations],
                                           [a.model_dump(mode="json") for a in i.adjustments])
    ctx.state.allocation = res
    ctx.deps.audit.append(ctx.case_id, "ALLOCATION_PROPOSED", "agent",
                          {"tool_call_id": ctx.call_id, "variance_paise": res.variance_paise,
                           "unexplained_paise": res.unexplained_paise})
    out = res.model_dump(mode="json")
    out["hint"] = ("unexplained_paise is within tolerance: call finish now." if abs(res.unexplained_paise) <= 100 else
                   "A gap remains: call request_evidence for what is missing, or finish if sources disagree.")
    return out


TOOL = Tool("propose_allocation", "Propose which invoices the receipt(s) pay and which adjustments (tds, "
            "credit_note, bank_charge, rounding) explain the gap. The variance engine validates each and returns "
            "unexplained_paise. Cite evidence_ids returned by earlier tools. Required before finish.", Input, _run)
