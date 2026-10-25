"""Tool registry. execute() never raises: every failure comes back as {"error": ..., "detail": ...}."""
from __future__ import annotations

from pydantic import ValidationError

from artemis.models import CoreError
from artemis.ports import IllegalTransition
from artemis.tools import (compute_withholding, find_credit_notes, finish, get_authorized_tax_credit_extract,
                           parse_remittance, propose_allocation, record_hypothesis, request_evidence,
                           resolve_customer, search_bank_receipts, search_ledger, search_remittance_email)
from artemis.tools.base import Tool, ToolContext

TOOLS: dict[str, Tool] = {t.name: t for t in (
    search_ledger.TOOL, search_bank_receipts.TOOL, search_remittance_email.TOOL, parse_remittance.TOOL,
    get_authorized_tax_credit_extract.TOOL, compute_withholding.TOOL, find_credit_notes.TOOL,
    resolve_customer.TOOL, propose_allocation.TOOL, request_evidence.TOOL, record_hypothesis.TOOL, finish.TOOL)}


def schemas() -> list[dict]:
    """OpenAI-style tool schemas generated from the Pydantic input models (no drift possible)."""
    return [{"type": "function", "function": {"name": t.name, "description": t.description,
                                              "parameters": t.input.model_json_schema()}}
            for t in TOOLS.values()]


def execute(name: str, args: dict, ctx: ToolContext) -> dict:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": "unknown_tool", "detail": f"{name!r}; available: {sorted(TOOLS)}"}
    try:
        inp = tool.input.model_validate(args)
    except ValidationError as e:
        return {"error": "invalid_input", "detail": e.json(include_url=False)}
    try:
        return tool.fn(ctx, inp)
    except CoreError as e:
        return {"error": e.code, "detail": e.detail}
    except IllegalTransition as e:
        return {"error": "refused", "detail": e.reason}
    except Exception as e:  # tools never raise into the loop
        return {"error": "internal", "detail": f"{type(e).__name__}: {e}"}
