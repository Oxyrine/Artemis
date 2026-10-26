"""Offline stand-in for the model: a rule-based 'oracle' agent that investigates a case using ONLY the tools the
real agent has (it reads the opening context and each tool's result, then decides the next call). It is free, so it
lets the whole pipeline run on all 40 cases without an API key; it is a pipeline check, not an LLM score.

For a gap it tries, in order of cheapness: nothing (variance 0), rounding, then the subset of {TDS, credit notes,
bank charge} that explains the variance. TDS is confirmed against the tax-credit extract: a row that agrees makes it
primary evidence, no row means 'likely, unconfirmed' + request_evidence (Probable), a row that disagrees is recorded
and the case finishes (Conflicting). Anything left over is unexplained; a receipt that matches an already-applied
invoice is a duplicate."""
from __future__ import annotations

import itertools
import json
import re
from datetime import date

from artemis.agent.llm import LLMResponse, ToolCallReq
from artemis.money import quarter_of

TOL = 100


def _parse_email(body: str) -> dict:
    """Stand-in for parse_remittance's inner LLM call: pull facts out of the email text."""
    deductions = []
    if re.search(r"TDS deducted", body):
        deductions.append({"kind": "tds", "amount": ""})
    m = re.search(r"credit note of Rs ([\d,]+)", body)
    if m:
        deductions.append({"kind": "credit note", "amount": m.group(1)})
    return {"invoice_refs": re.findall(r"INV-\d+", body), "amounts": [], "stated_deductions": deductions,
            "claimed_utrs": sorted(set(re.findall(r"UTR\d+", body)))}


def _plan(core, case_id: str, oc: dict):
    """Generator: yields (tool, args), receives each tool's result dict."""
    receipts = oc.get("receipts") or [oc["receipt"]]
    rec, utrs = receipts[0], [r["utr"] for r in receipts]
    total = sum(r["amount"] for r in receipts)
    cust = oc["customer_candidates"][0]["customer_id"]
    quarter = quarter_of(date.fromisoformat(rec["value_date"]))
    inv_ids, v = sorted(oc["best_combination"]["invoice_ids"]), oc["best_combination"]["variance_paise"]
    gross = {i["id"]: i["gross_amount"] for i in oc["open_invoices"]}

    def alloc(ids):
        return [dict(invoice_id=i, amount_paise=gross[i]) for i in ids]

    def propose(ids, adjustments):
        return ("propose_allocation", dict(utrs=utrs, allocations=alloc(ids), adjustments=adjustments))

    yield ("record_hypothesis", dict(text="The receipt differs from the open invoices: find out why", kind="unexplained"
                                     if not v else "tds", status="open"))
    ledger = yield ("search_ledger", dict(customer_id=cust))
    if abs(v) <= TOL:  # nothing to explain, or rounding
        rc = yield ("search_bank_receipts", dict(narration_text=utrs[0]))
        adjs = [dict(kind="rounding", amount_paise=v, evidence_ids=rc["evidence_ids"] + ledger["evidence_ids"])] if v else []
        yield propose(inv_ids, adjs)
        yield ("finish", dict(case_id=case_id, summary="Closed" if not v else "Rounding"))
        return
    emails = yield ("search_remittance_email", dict(utr=utrs[0]))
    parsed = None
    if emails.get("emails"):
        parsed = yield ("parse_remittance", dict(email_id=emails["emails"][0]["id"]))
    rc = yield ("search_bank_receipts", dict(narration_text=utrs[0]))
    options: list[tuple[str, int, list[str], dict]] = []  # (kind, amount, evidence, extra args)
    calc = {"expected_paise": 0, "evidence_ids": []}
    if inv_ids:
        calc = yield ("compute_withholding", dict(customer_id=cust, invoice_ids=inv_ids, transaction_date=rec["value_date"]))
        if calc["expected_paise"]:
            options.append(("tds", calc["expected_paise"], calc["evidence_ids"], {}))
        cns = yield ("find_credit_notes", dict(customer_id=cust, invoice_ids=inv_ids))
        for row, ev in zip(cns["credit_notes"], cns["evidence_ids"]):
            options.append(("credit_note", row["amount"], [ev], {"credit_note_id": row["id"]}))
    charges = sum(r["bank_charges"] for r in receipts)
    if charges:
        options.append(("bank_charge", charges, rc["evidence_ids"], {}))
    chosen = next((c for n in (1, 2, 3) for c in itertools.combinations(options, n)
                   if abs(v - sum(o[1] for o in c)) <= TOL), None)
    if chosen is None:  # unexplained: is it a duplicate of an invoice that is already applied?
        dup = yield ("search_ledger", dict(customer_id=cust, amount_paise=total, status="applied"))
        if dup["invoices"]:
            gross.update({i["id"]: i["gross_amount"] for i in dup["invoices"]})
            yield ("record_hypothesis", dict(text="Duplicate payment of an applied invoice", kind="duplicate",
                                             status="supported"))
            yield propose([dup["invoices"][0]["id"]], [])
        else:
            yield ("record_hypothesis", dict(text="No explanation found for the shortfall", kind="unexplained",
                                             status="supported"))
            yield propose(inv_ids, [])
        yield ("finish", dict(case_id=case_id, summary="Unexplained"))
        return
    adjs, conflict, unconfirmed = [], False, False
    for kind, amt, ev, extra in chosen:
        if kind == "tds":
            tax = yield ("get_authorized_tax_credit_extract", dict(customer_id=cust, quarter=quarter))
            rows = [r for r in tax["rows"] if r["transaction_date"] == rec["value_date"]]
            if not rows:  # filed later: TDS likely but unconfirmed -> supporting evidence only
                unconfirmed = True
                ev = ev + (parsed["evidence_ids"] if parsed else [])
            else:
                ev = ev + tax["evidence_ids"]
                conflict = conflict or abs(rows[0]["amount_credited"] - amt) > TOL
        adjs.append(dict(kind=kind, amount_paise=amt, evidence_ids=ev, **extra))
    if conflict:
        yield ("record_hypothesis", dict(text="The tax credit disagrees with the computed TDS", kind="tds",
                                         status="rejected", reason="sources disagree"))
    elif unconfirmed:
        yield ("record_hypothesis", dict(text="TDS likely, unconfirmed", kind="tds", status="open",
                                         reason="no tax credit row filed yet"))
    yield propose(inv_ids, adjs)
    if unconfirmed:
        yield ("request_evidence", dict(what="TDS certificate / tax credit for the quarter", from_whom="customer"))
    yield ("finish", dict(case_id=case_id, summary="done"))


def golden_agent(core, case_id: str):
    """Returns a callable(messages) -> LLMResponse for ScriptedLLM. Reads only what the CoreService port exposes."""
    oc = core.opening_context(case_id)
    plan, state = _plan(core, case_id, oc), {"n": 0, "started": False}

    def call(messages: list[dict]) -> LLMResponse:
        if messages[0]["content"].startswith("Extract facts"):  # parse_remittance's inner call
            return LLMResponse(text=json.dumps(_parse_email(messages[1]["content"])), tokens_in=50, tokens_out=30)
        try:
            if not state["started"]:
                state["started"], step = True, next(plan)
            else:
                step = plan.send(json.loads(messages[-1]["content"]))
        except StopIteration:
            step = ("finish", dict(case_id=case_id, summary="done"))
        state["n"] += 1
        return LLMResponse(tool_calls=[ToolCallReq(f"call_{state['n']}", step[0], step[1])], tokens_in=200, tokens_out=40)

    return call
