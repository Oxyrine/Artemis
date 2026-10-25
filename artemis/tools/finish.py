from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    case_id: str
    summary: str


def _run(ctx, i: Input) -> dict:
    if i.case_id != ctx.case_id:
        return {"error": "not_found", "detail": f"you are investigating {ctx.case_id}, not {i.case_id}"}
    ctx.state.finished, ctx.state.summary = True, i.summary
    return {"finished": True}


TOOL = Tool("finish", "End the investigation and trigger grading. Only allowed after propose_allocation.", Input, _run)
