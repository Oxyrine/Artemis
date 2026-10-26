"""Variance engine. variance = gross of allocated invoices - receipts in the case;
unexplained = variance - validated adjustments. Each adjustment is validated by its own rule and only validated
ones count. Tolerance for 'closes to zero' is 100 paise."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from artemis.db import BankReceipt, CreditNote, Customer, Invoice
from artemis.models import (AdjustmentKind, AdjustmentResult, AllocationLine, AllocationResult, CoreError)
from artemis.rules import withholding

TOL = 100


def propose(s: Session, case_id: str, utrs: list[str], allocations: list[dict], adjustments: list[dict]) -> AllocationResult:
    receipts = []
    for u in utrs:
        r = s.get(BankReceipt, u)
        if r is None:
            raise CoreError("not_found", f"receipt {u} does not exist")
        receipts.append(r)
    lines = [AllocationLine(**a) for a in allocations]
    invoices = []
    for a in lines:
        inv = s.get(Invoice, a.invoice_id)
        if inv is None:
            raise CoreError("not_found", f"invoice {a.invoice_id} does not exist")
        invoices.append(inv)
    invoiced, received = sum(i.gross_amount for i in invoices), sum(r.amount for r in receipts)
    variance = invoiced - received
    remaining, results = variance, []
    for adj in sorted(adjustments, key=lambda a: a["kind"] == AdjustmentKind.ROUNDING):  # rounding judged last
        kind, amt = adj["kind"], adj["amount_paise"]
        ok, rule = _validate(s, kind, amt, adj, invoices, receipts, remaining)
        if ok:
            remaining -= amt
        results.append(AdjustmentResult(**adj, validated=ok, validated_by_rule=rule if ok else ""))
    return AllocationResult(case_id=case_id, utrs=utrs, allocations=lines, adjustments=results,
                            invoiced_paise=invoiced, received_paise=received, variance_paise=variance,
                            unexplained_paise=remaining)


def _validate(s, kind, amt, adj, invoices, receipts, remaining) -> tuple[bool, str]:
    if kind == AdjustmentKind.TDS:
        if not invoices:
            return False, ""
        cust = s.get(Customer, invoices[0].customer_id)
        exp = withholding.compute(cust, invoices, receipts[0].value_date)["expected_paise"]
        return abs(amt - exp) <= TOL, f"tds equals compute_withholding ({exp} paise) within {TOL}"
    if kind == AdjustmentKind.CREDIT_NOTE:
        cn = s.get(CreditNote, adj.get("credit_note_id") or "")
        ok = cn is not None and cn.amount == amt and cn.invoice_id in {i.id for i in invoices} \
            and cn.customer_id == invoices[0].customer_id
        return ok, "credit note exists for this customer and invoice, amount equal"
    if kind == AdjustmentKind.BANK_CHARGE:
        return amt == sum(r.bank_charges for r in receipts) and amt > 0, "equals bank_charges on the statement line"
    if kind == AdjustmentKind.ROUNDING:
        return abs(amt) <= TOL and amt == remaining, f"|x| <= {TOL} paise and it is the only remaining gap"
    return False, ""
