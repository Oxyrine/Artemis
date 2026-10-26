"""Offline stand-in for the model: a rule-based 'golden agent' that reads tool observations and branches the
way the spec's acceptance test expects (Verified / Probable / Conflicting twins). Free to run; used by tests
and by `eval.run --scripted` so the whole pipeline can be exercised without an API key."""
from __future__ import annotations

import json
import re
from datetime import date

from artemis.agent.llm import LLMResponse, ToolCallReq
from artemis.money import quarter_of


def golden_agent(core, case_id: str):
    """Reads only what the CoreService port exposes, so it drives the fixture fake and Lane A's SQL core alike."""
    oc = core.opening_context(case_id)
    rec = oc["receipt"]
    cust = oc["customer_candidates"][0]["customer_id"]
    inv_ids = sorted(oc["best_combination"]["invoice_ids"])
    gross = {i["id"]: i["gross_amount"] for i in oc["open_invoices"]}
    email_id = core.search_remittance_email(utr=rec["utr"]).data["emails"][0]["id"]
    quarter = quarter_of(date.fromisoformat(rec["value_date"]))
    plan: list[tuple[str, dict]] = [
        ("record_hypothesis", dict(text="Short payment is explained by TDS", kind="tds", status="open")),
        ("search_ledger", dict(customer_id=cust)),
        ("search_remittance_email", dict(customer_id=cust)),
        ("parse_remittance", dict(email_id=email_id)),
        ("compute_withholding", dict(customer_id=cust, invoice_ids=inv_ids, transaction_date=rec["value_date"])),
        ("get_authorized_tax_credit_extract", dict(customer_id=cust, quarter=quarter))]
    seen: dict[str, dict] = {}
    alloc = [dict(invoice_id=i, amount_paise=gross[i]) for i in inv_ids]

    def propose(ev: list[str], amount: int) -> tuple[str, dict]:
        return ("propose_allocation", dict(utrs=[rec["utr"]], allocations=alloc,
                adjustments=[dict(kind="tds", amount_paise=amount, evidence_ids=ev)]))

    def call(messages: list[dict]) -> LLMResponse:
        if messages[0]["content"].startswith("Extract facts"):  # parse_remittance's inner call
            body = messages[1]["content"]
            return LLMResponse(text=json.dumps({"invoice_refs": re.findall(r"INV-\d+", body),
                                                "amounts": ["15,08,000"], "claimed_utrs": [rec["utr"]],
                                                "stated_deductions": [{"kind": "tds", "amount": ""}]}),
                               tokens_in=50, tokens_out=30)
        n = sum(m["role"] == "assistant" for m in messages)
        if n:  # remember what the previous tool returned
            seen[plan[n - 1][0]] = json.loads(messages[-1]["content"])
        if n == 6:  # branch on the tax-credit extract, exactly like the spec's twins
            calc, rows = seen["compute_withholding"], seen["get_authorized_tax_credit_extract"]["rows"]
            exp, ev_calc = calc["expected_paise"], calc["evidence_ids"]
            if not rows:  # Probable twin
                plan.extend([("record_hypothesis", dict(text="TDS likely, unconfirmed", kind="tds", status="open",
                                                         reason="no tax credit row filed yet")),
                             propose(ev_calc + seen["parse_remittance"]["evidence_ids"], exp),
                             ("request_evidence", dict(what="TDS certificate / tax credit for the quarter",
                                                       from_whom="customer")),
                             ("finish", dict(case_id=case_id, summary="TDS likely but unconfirmed"))])
            elif rows[0]["amount_credited"] == exp:  # Verified twin
                plan.extend([propose(ev_calc + seen["get_authorized_tax_credit_extract"]["evidence_ids"], exp),
                             ("finish", dict(case_id=case_id, summary="Closed to zero with primary evidence"))])
            else:  # Conflicting twin
                plan.extend([("record_hypothesis", dict(text="Tax credit disagrees with computed TDS", kind="tds",
                                                         status="rejected", reason="sources disagree")),
                             propose(ev_calc + seen["get_authorized_tax_credit_extract"]["evidence_ids"], exp),
                             ("finish", dict(case_id=case_id, summary="Sources disagree; stopping"))])
        name, args = plan[n]
        return LLMResponse(tool_calls=[ToolCallReq(f"call_{n}", name, args)], tokens_in=200, tokens_out=40)

    return call
