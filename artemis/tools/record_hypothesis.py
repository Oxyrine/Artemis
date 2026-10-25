from pydantic import BaseModel

from artemis.models import Hypothesis, HypothesisKind, HypothesisStatus
from artemis.tools.base import Tool


class Input(BaseModel):
    text: str
    kind: HypothesisKind
    status: HypothesisStatus
    reason: str = ""


def _run(ctx, i: Input) -> dict:
    h = Hypothesis(id=ctx.deps.store.next_id("HYP"), run_id=ctx.run_id, step=ctx.step, **i.model_dump())
    ctx.deps.store.add_hypothesis(h)
    ctx.deps.audit.append(ctx.case_id, "HYPOTHESIS_RECORDED", "agent",
                          {"hypothesis_id": h.id, "kind": h.kind, "status": h.status})
    return {"hypothesis_id": h.id}


TOOL = Tool("record_hypothesis", "Record a hypothesis you open, support or reject, BEFORE using an evidence "
            "tool. Revise by recording again with a new status.", Input, _run)
