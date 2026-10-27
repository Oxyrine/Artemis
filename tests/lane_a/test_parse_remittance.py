import json

from artemis.agent.llm import LLMResponse
from artemis.tools import parse_remittance
from artemis.tools.base import ToolContext


class StubLLM:
    model = "stub"

    def __init__(self, payload):
        self.payload = payload

    def chat(self, messages, json_mode=False):
        return LLMResponse(text=json.dumps(self.payload), tokens_in=1, tokens_out=1)


def run_tool(real, payload):
    email_id = real.core.search_remittance_email(utr="UTR839201").data["emails"][0]["id"]
    ctx = ToolContext(deps=real, llm=StubLLM(payload), case_id="CASE-0007", run_id="RUN-0001")
    return parse_remittance.TOOL.fn(ctx, parse_remittance.Input(email_id=email_id))


def test_invoice_amounts_are_converted_to_paise_in_code(real):
    out = run_tool(real, {"invoice_refs": ["INV-1042"], "invoice_amounts": [
        {"invoice_ref": "INV-1042", "amount": "11,70,000"}, {"invoice_ref": "INV-1043", "amount": ""}]})
    assert out["invoice_amounts"] == [{"invoice_ref": "INV-1042", "amount_paise": 117_000_000},
                                      {"invoice_ref": "INV-1043", "amount_paise": None}]


def test_output_without_invoice_amounts_still_parses(real):
    assert run_tool(real, {"invoice_refs": ["INV-1042"]})["invoice_amounts"] == []

