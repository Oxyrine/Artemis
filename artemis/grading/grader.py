"""Evidence grader: VERIFIED / PROBABLE / INSUFFICIENT / CONFLICTING, checked in code (no LLM).

  CONFLICTING  any contradiction flag, whatever the variance
  INSUFFICIENT unexplained variance != 0 after validated adjustments (or nothing to grade, or a duplicate)
  VERIFIED     unexplained == 0 within tolerance AND every validated adjustment rests on >=1 RELEVANT primary
               evidence item AND no contradiction
  PROBABLE     unexplained == 0 AND some adjustment rests only on supporting evidence AND no contradiction

Relevant primary evidence per adjustment kind: tds -> a tax-credit extract row; credit_note -> an issued ERP
credit note; bank_charge / rounding -> the bank receipt or the ERP invoice. A flag side is an evidence id when the
agent retrieved the item, otherwise 'table:id' (the grader also looks for contradictions the agent did not fetch)."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from artemis.db import Allocation, BankReceipt, Case, CreditNote, Customer, Invoice, RemittanceEmail, TaxCredit
from artemis.matching.names import normalize_name
from artemis.models import (AdjustmentKind, AllocationResult, ContradictionFlag, Evidence, EvidenceStatus, Grade,
                            Tier)
from artemis.rules import withholding

TOL = 100
INV_REF = re.compile(r"INV-\d+")
_PRIMARY_FOR = {AdjustmentKind.TDS: ("tax_credits",), AdjustmentKind.CREDIT_NOTE: ("credit_notes",),
                AdjustmentKind.BANK_CHARGE: ("bank_receipts", "invoices"),
                AdjustmentKind.ROUNDING: ("bank_receipts", "invoices")}


def grade(s: Session, case_id: str, allocation: AllocationResult | None, evidence: list[Evidence]) -> Grade:
    case = s.get(Case, case_id)
    receipts = list(s.scalars(select(BankReceipt).where(BankReceipt.case_id == case_id)))
    cust = s.get(Customer, case.customer_id) if case and case.customer_id else None
    ev = {e.id: e for e in evidence}
    by_src = {(e.source_table, e.source_id): e.id for e in evidence}

    def side(table: str, sid: str) -> str:
        return by_src.get((table, sid), f"{table}:{sid}")

    invs = [s.get(Invoice, a.invoice_id) for a in allocation.allocations] if allocation else []
    expected = None
    if cust and invs and receipts:
        expected = withholding.compute(cust, invs, receipts[0].value_date)["expected_paise"]
    calc = next((e.id for e in evidence if e.kind == "withholding_calc"), f"rules:{expected}")
    flags: list[ContradictionFlag] = []

    def flag(code: int, detail: str, a: str, b: str) -> None:
        if not any(f.code == code and {f.evidence_a, f.evidence_b} == {a, b} for f in flags):
            flags.append(ContradictionFlag(code=code, detail=detail, evidence_a=a, evidence_b=b))

    # 1 + 2: tax-credit rows (those the agent cited, plus any that exist for this deductor on the payment date)
    pay_dates = {r.value_date for r in receipts}
    tcs = {e.source_id: s.get(TaxCredit, e.source_id) for e in evidence if e.source_table == "tax_credits"}
    if cust:
        for tc in s.scalars(select(TaxCredit).where(TaxCredit.deductor_tan == cust.tan,
                                                    TaxCredit.transaction_date.in_(pay_dates))):
            tcs.setdefault(tc.id, tc)
    for tc in filter(None, tcs.values()):
        if cust and (tc.deductor_tan != cust.tan or normalize_name(tc.deductor_name) != normalize_name(cust.legal_name)):
            flag(2, f"deductor {tc.deductor_tan}/{tc.deductor_name} is not the case's customer", side("tax_credits", tc.id),
                 side("customers", cust.id))
        elif expected is not None and tc.transaction_date in pay_dates and abs(tc.amount_credited - expected) > TOL:
            flag(1, f"tax credit {tc.amount_credited} vs computed TDS {expected} (paise)", calc, side("tax_credits", tc.id))
    # 3, 5, 6, 7: what the (parsed) remittance emails claim
    erp_cns = [c for c in s.scalars(select(CreditNote).where(CreditNote.source == "erp")) if c.invoice_id in
               {i.id for i in invs}]
    for e in (e for e in evidence if e.source_table == "remittance_emails"):
        em = s.get(RemittanceEmail, e.source_id)
        p = (em.parsed if em else None) or {}
        for d in p.get("stated_deductions", []):
            amt = d.get("amount_paise")
            if amt is None:
                continue
            if d.get("kind") == "tds" and expected is not None and abs(amt - expected) > TOL:
                flag(3, f"email states TDS {amt} vs computed {expected} (paise)", e.id, calc)
            if d.get("kind") == "credit_note":
                for cn in erp_cns:
                    if abs(amt - cn.amount) > TOL:
                        flag(5, f"email credit note {amt} vs ERP {cn.id} {cn.amount} (paise)", e.id, side("credit_notes", cn.id))
        for ia in p.get("invoice_amounts", []):
            inv = s.get(Invoice, ia.get("invoice_ref", ""))
            if inv and ia.get("amount_paise") not in (None, inv.gross_amount):
                flag(6, f"email says {ia['amount_paise']} for {inv.id}, ERP says {inv.gross_amount} (paise)", e.id,
                     side("invoices", inv.id))
        for utr in p.get("claimed_utrs", []):
            if s.get(BankReceipt, utr) is None:
                flag(7, f"email claims payment {utr} but the bank statement has no such receipt", e.id,
                     f"bank_receipts:{utr}")
    # 4: the narration cites an invoice that belongs to a different customer
    for r in receipts:
        for ref in set(INV_REF.findall(r.narration)):
            inv = s.get(Invoice, ref)
            if inv and cust and inv.customer_id != cust.id:
                flag(4, f"narration cites {ref}, which belongs to {inv.customer_id}, not {cust.id}",
                     side("bank_receipts", r.utr), side("invoices", ref))

    dup = _is_duplicate(s, case_id, cust, receipts)
    unexplained = allocation.unexplained_paise if allocation else None
    if flags:
        return Grade(status=EvidenceStatus.CONFLICTING, unexplained_paise=unexplained, flags=flags, duplicate=dup)
    if dup:
        return Grade(status=EvidenceStatus.INSUFFICIENT, unexplained_paise=unexplained, duplicate=True,
                     recommendation="refund_or_hold: only a controller can approve")
    if allocation is None or abs(allocation.unexplained_paise) > TOL:
        return Grade(status=EvidenceStatus.INSUFFICIENT, unexplained_paise=unexplained)

    def primary(a) -> bool:
        return any(i in ev and ev[i].tier == Tier.PRIMARY and ev[i].source_table in _PRIMARY_FOR[a.kind]
                   for i in a.evidence_ids)
    ok = all(primary(a) for a in allocation.adjustments if a.validated)
    return Grade(status=EvidenceStatus.VERIFIED if ok else EvidenceStatus.PROBABLE, unexplained_paise=unexplained)


def _is_duplicate(s: Session, case_id: str, cust: Customer | None, receipts: list[BankReceipt]) -> bool:
    """The receipt's only matching invoice is already applied (by something other than this case)."""
    if cust is None:
        return False
    case = s.get(Case, case_id)
    # An invoice a case itself applied is not a duplicate of itself; but a PROPOSED allocation (which is also stored as an
    # allocation row) onto an invoice that is already applied is exactly the duplicate we must not clear.
    mine = ({a.invoice_id for a in s.scalars(select(Allocation).where(Allocation.case_id == case_id))}
            if case and case.state in ("APPLIED", "AUTO_CLOSED") else set())
    amounts = {r.amount for r in receipts} | {sum(r.amount for r in receipts)}
    for amt in amounts:
        match = [i for i in s.scalars(select(Invoice).where(Invoice.customer_id == cust.id, Invoice.gross_amount == amt))
                 if i.id not in mine]
        if match and all(i.status == "applied" for i in match):
            return True
    return False
