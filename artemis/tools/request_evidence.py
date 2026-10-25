from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    what: str
    from_whom: str


def _run(ctx, i: Input) -> dict:
    # The loop moves the case to AWAITING_EVIDENCE through the policy engine after grading, so a
    # request followed by an Insufficient/Conflicting grade can't strand the case in an illegal state.
    ctx.state.evidence_requested = True
    rid = ctx.deps.store.next_id("ER")
    ctx.deps.audit.append(ctx.case_id, "EVIDENCE_REQUESTED", "agent",
                          {"request_id": rid, "tool_call_id": ctx.call_id, "what": i.what, "from_whom": i.from_whom})
    return {"request_id": rid, "logged": True}


TOOL = Tool("request_evidence", "Log a request for missing evidence (e.g. the TDS certificate) from a named "
            "party. Use when propose_allocation leaves a gap you cannot close.", Input, _run)
