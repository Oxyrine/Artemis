"""SqlCore: Lane A's implementation of ports.CoreService over the database. Everything deterministic, no LLM.
Money is integer paise in and out; search methods return CoreResult(data, refs) where refs become Evidence rows
(tiers per the spec: bank receipt / ERP invoice / tax-credit row / issued credit note are primary, email and
agreed-not-issued credit notes supporting, calculations and entity matches derived)."""
from __future__ import annotations

import itertools
import re
from datetime import date

from sqlalchemy import select

from artemis.db import (Adjustment, Allocation, BankReceipt, Case, CreditNote, Customer, Db, Invoice,
                        RemittanceEmail, TaxCredit)
from artemis.grading import grader, variance
from artemis.grading.policy import SqlPolicy
from artemis.ingest.load_all import ENV_DIR, load_all
from artemis.matching import matcher, names
from artemis.models import (AllocationResult, CaseState, CoreError, CoreResult, Evidence, EvidenceRef, Grade, Tier)
from artemis.money import quarter_of
from artemis.ports import AuditSink
from artemis.rules import withholding

INV_REF = re.compile(r"INV-\d+")


def _row(o, *cols: str) -> dict:
    return {c: getattr(o, c) for c in cols}


def _ref(kind: str, tier: Tier, table: str, sid: str, excerpt: str = "") -> EvidenceRef:
    return EvidenceRef(kind=kind, tier=tier, source_table=table, source_id=sid, excerpt=excerpt)


_INV = ("id", "customer_id", "invoice_date", "due_date", "taxable_value", "gst_amount", "gross_amount", "po_ref", "status")
_RCPT = ("utr", "value_date", "amount", "payer_name_raw", "narration", "bank_charges", "resolved_customer_id", "case_id")
_TC = ("id", "deductor_name", "deductor_tan", "our_pan", "quarter", "amount_credited", "tds_section_ref", "transaction_date")
_CN = ("id", "customer_id", "invoice_id", "amount", "issued_on", "source", "status")


class SqlCore:
    def __init__(self, db: Db, policy: SqlPolicy, audit: AuditSink, env_dir=ENV_DIR):
        self.db, self.policy, self.audit, self.env_dir = db, policy, audit, env_dir

    # ---- environment lifecycle (POST /reset, eval)
    def reset(self) -> dict:
        """Reload the environment to its seed state: drop everything, ingest data/env, nothing matched yet."""
        self.db.reset()
        return load_all(self.db, self.env_dir)

    def auto_close(self) -> list[str]:
        """Run the matcher: create the cases and auto-close the exact matches. Returns the AUTO_CLOSED case ids."""
        return matcher.run(self.db, self.policy, self.audit)

    def new_case_ids(self) -> list[str]:
        with self.db.tx() as s:
            return list(s.scalars(select(Case.id).where(Case.state == "NEW").order_by(Case.id)))

    # ---- opening context (built in code for the agent)
    def opening_context(self, case_id: str) -> dict:
        with self.db.tx() as s:
            case = s.get(Case, case_id)
            if case is None:
                raise CoreError("not_found", f"case {case_id}")
            receipts = list(s.scalars(select(BankReceipt).where(BankReceipt.case_id == case_id).order_by(BankReceipt.utr)))
            first = receipts[0]
            res = names.resolve(s, first.payer_name_raw, first.narration)
            top = res.customer_id or (res.candidates[0]["customer_id"] if res.candidates else None)
            open_inv = [_row(i, *_INV) for i in s.scalars(select(Invoice).where(
                Invoice.customer_id == top, Invoice.status.in_(("open", "partially_applied"))).order_by(Invoice.id))]
            total = sum(r.amount for r in receipts)
            cited = sorted({x for r in receipts for x in INV_REF.findall(r.narration)})
            by_id = {i["id"]: i for i in open_inv}
            if cited and all(c in by_id for c in cited):  # the payer's own narration names open invoices: use those
                best = tuple(by_id[c] for c in cited)
            else:  # otherwise the open invoices (up to three) whose gross is nearest the receipt
                combos = [c for n in (1, 2, 3) for c in itertools.combinations(open_inv, n)]
                best = min(combos, key=lambda c: abs(sum(i["gross_amount"] for i in c) - total), default=())
            return {"case_id": case_id, "receipt": _row(first, *_RCPT),
                    "receipts": [_row(r, *_RCPT) for r in receipts], "customer_candidates": res.candidates,
                    "narration_invoice_refs": cited,
                    "open_invoices": open_inv,
                    "best_combination": {"invoice_ids": [i["id"] for i in best],
                                         "variance_paise": sum(i["gross_amount"] for i in best) - total}}

    # ---- evidence tools
    def search_ledger(self, customer_id, amount_paise=None, date_from=None, date_to=None, status=None) -> CoreResult:
        with self.db.tx() as s:
            q = select(Invoice).where(Invoice.customer_id == customer_id, Invoice.status == (status or "open"))
            if amount_paise is not None:
                q = q.where(Invoice.gross_amount == amount_paise)
            if date_from:
                q = q.where(Invoice.invoice_date >= date_from)
            if date_to:
                q = q.where(Invoice.invoice_date <= date_to)
            rows = list(s.scalars(q.order_by(Invoice.id)))
            return CoreResult(data={"invoices": [_row(i, *_INV) for i in rows]},
                              refs=[_ref("invoice", Tier.PRIMARY, "invoices", i.id, f"gross_paise={i.gross_amount}")
                                    for i in rows])

    def search_bank_receipts(self, customer_id=None, amount_paise=None, date_from=None, date_to=None,
                             narration_text=None) -> CoreResult:
        with self.db.tx() as s:
            q = select(BankReceipt)
            if customer_id:
                q = q.where(BankReceipt.resolved_customer_id == customer_id)
            if amount_paise is not None:
                q = q.where(BankReceipt.amount == amount_paise)
            if date_from:
                q = q.where(BankReceipt.value_date >= date_from)
            if date_to:
                q = q.where(BankReceipt.value_date <= date_to)
            if narration_text:
                q = q.where(BankReceipt.narration.ilike(f"%{narration_text}%"))
            rows = list(s.scalars(q.order_by(BankReceipt.utr)))  # includes receipts that belong to other cases
            return CoreResult(data={"receipts": [_row(r, *_RCPT) for r in rows]},
                              refs=[_ref("bank_receipt", Tier.PRIMARY, "bank_receipts", r.utr, f"amount_paise={r.amount}")
                                    for r in rows])

    def search_remittance_email(self, customer_id=None, utr=None, invoice_ids=None, text=None) -> CoreResult:
        with self.db.tx() as s:
            def hit(e: RemittanceEmail) -> bool:
                body = e.body_text.lower()
                return bool((customer_id and e.customer_id == customer_id) or (utr and utr.lower() in body)
                            or any(i.lower() in body for i in invoice_ids or []) or (text and text.lower() in body))
            rows = [e for e in s.scalars(select(RemittanceEmail).order_by(RemittanceEmail.id)) if hit(e)]
            return CoreResult(data={"emails": [{"id": e.id, "subject": e.subject, "excerpt": e.body_text[:160]}
                                               for e in rows]},
                              refs=[_ref("remittance_email", Tier.SUPPORTING, "remittance_emails", e.id, e.body_text[:160])
                                    for e in rows])

    def get_email(self, email_id) -> CoreResult:
        with self.db.tx() as s:
            e = s.get(RemittanceEmail, email_id)
            if e is None:
                raise CoreError("not_found", f"email {email_id}")
            return CoreResult(data={"id": e.id, "body_text": e.body_text},
                              refs=[_ref("remittance_email", Tier.SUPPORTING, "remittance_emails", e.id, e.body_text[:160])])

    def save_parsed_email(self, email_id: str, parsed: dict) -> None:
        """Store Lane B's parse_remittance output. A credit note the email says was agreed but not issued becomes an
        email_only / agreed_not_issued credit-note row (supporting evidence), so the variance engine can validate it."""
        with self.db.tx() as s:
            e = s.get(RemittanceEmail, email_id)
            if e is None:
                raise CoreError("not_found", f"email {email_id}")
            e.parsed = parsed
            refs = [r for r in parsed.get("invoice_refs", []) if s.get(Invoice, r)]
            for d in parsed.get("stated_deductions", []):
                if "credit" not in str(d.get("kind", "")).lower() or not d.get("amount_paise") or len(refs) != 1:
                    continue
                inv = s.get(Invoice, refs[0])
                dup = s.scalar(select(CreditNote).where(CreditNote.invoice_id == inv.id,
                                                        CreditNote.amount == d["amount_paise"]))
                if dup is None:
                    n = len(list(s.scalars(select(CreditNote).where(CreditNote.source == "email_only")))) + 1
                    s.add(CreditNote(id=f"CN-E{n:03d}", customer_id=inv.customer_id, invoice_id=inv.id,
                                     amount=d["amount_paise"], issued_on=e.received_at[:10], source="email_only",
                                     status="agreed_not_issued"))

    def get_authorized_tax_credit_extract(self, customer_id, quarter) -> CoreResult:
        with self.db.tx() as s:
            c = s.get(Customer, customer_id)
            if c is None:
                raise CoreError("not_found", f"customer {customer_id}")
            rows = list(s.scalars(select(TaxCredit).where(TaxCredit.deductor_tan == c.tan, TaxCredit.quarter == quarter)
                                  .order_by(TaxCredit.id)))
            return CoreResult(data={"rows": [_row(t, *_TC) for t in rows]},
                              refs=[_ref("tax_credit", Tier.PRIMARY, "tax_credits", t.id,
                                         f"amount_credited_paise={t.amount_credited}") for t in rows])

    def compute_withholding(self, customer_id, invoice_ids, transaction_date) -> CoreResult:
        with self.db.tx() as s:
            c = s.get(Customer, customer_id)
            if c is None:
                raise CoreError("not_found", f"customer {customer_id}")
            invs = []
            for i in invoice_ids:
                inv = s.get(Invoice, i)
                if inv is None:
                    raise CoreError("not_found", f"invoice {i} does not exist")
                invs.append(inv)
            data = withholding.compute(c, invs, transaction_date)
            return CoreResult(data=data, refs=[_ref("withholding_calc", Tier.DERIVED, "rules", data["rule_version"],
                                                    f"expected_paise={data['expected_paise']}")])

    def find_credit_notes(self, customer_id, invoice_ids=None) -> CoreResult:
        with self.db.tx() as s:
            q = select(CreditNote).where(CreditNote.customer_id == customer_id)
            if invoice_ids:
                q = q.where(CreditNote.invoice_id.in_(invoice_ids))
            rows = list(s.scalars(q.order_by(CreditNote.id)))
            return CoreResult(data={"credit_notes": [_row(c, *_CN) for c in rows]},
                              refs=[_ref("credit_note", Tier.PRIMARY if c.status == "issued" else Tier.SUPPORTING,
                                         "credit_notes", c.id, f"amount_paise={c.amount}") for c in rows])

    def resolve_customer(self, name_raw) -> CoreResult:
        with self.db.tx() as s:
            res = names.resolve(s, name_raw)
            refs = [_ref("entity_match", Tier.DERIVED, "customer_aliases", f"{name_raw}->{c['customer_id']}",
                         f"score={c['score']}") for c in res.candidates[:1]]
            return CoreResult(data={"candidates": res.candidates}, refs=refs)

    # ---- variance engine + grader
    def _absorb_receipts(self, s, case_id: str, utrs: list[str]) -> None:
        """A receipt the agent links to this case but that sits in another case moves here. A case left with no receipts
        becomes MERGED with a pointer (through the policy engine, so the move is audited). Only a case nobody has started
        (NEW) can be absorbed: a receipt in an investigated, applied or closed case is a conflict, not a merge."""
        for utr in dict.fromkeys(utrs):
            r = s.get(BankReceipt, utr)
            if r is None or r.case_id in (None, case_id):
                continue
            donor = s.get(Case, r.case_id)
            if donor.state != CaseState.NEW.value:
                raise CoreError("conflict", f"receipt {utr} belongs to {donor.id}, which is {donor.state}: only a case that "
                                            f"has not been investigated can be merged")
            r.case_id = case_id
            s.flush()
            if not s.scalars(select(BankReceipt.utr).where(BankReceipt.case_id == donor.id)).first():
                donor.merged_into = case_id
                self.policy.apply(s, donor.id, CaseState.MERGED, "agent")

    def propose_allocation(self, case_id, utrs, allocations, adjustments) -> AllocationResult:
        with self.db.tx() as s:
            case = s.get(Case, case_id)
            if case is None:
                raise CoreError("not_found", f"case {case_id}")
            res = variance.propose(s, case_id, utrs, allocations, adjustments)
            self._absorb_receipts(s, case_id, utrs)
            for model in (Allocation, Adjustment):  # the latest proposal replaces the previous one
                for old in s.scalars(select(model).where(model.case_id == case_id)):
                    s.delete(old)
            s.flush()
            s.add_all([Allocation(case_id=case_id, invoice_id=a.invoice_id, amount_paise=a.amount_paise)
                       for a in res.allocations])
            s.add_all([Adjustment(case_id=case_id, kind=a.kind.value, amount_paise=a.amount_paise,
                                  evidence_ids=a.evidence_ids, validated=a.validated, validated_by_rule=a.validated_by_rule)
                       for a in res.adjustments])
            case.variance_paise, case.unexplained_paise = res.variance_paise, res.unexplained_paise
            return res

    def grade(self, case_id, allocation, evidence: list[Evidence]) -> Grade:
        with self.db.tx() as s:
            g = grader.grade(s, case_id, allocation, evidence)
            case = s.get(Case, case_id)
            case.evidence_status, case.duplicate = g.status.value, g.duplicate
            return g

    # (quarter helper kept here so callers need not import money)
    @staticmethod
    def financial_quarter(iso_date: str) -> int:
        return quarter_of(date.fromisoformat(iso_date))
