"""Fixture-backed stand-in for Lane A's CoreService. Deliberately minimal: just enough variance
engine / grader behaviour to drive B's loop on the hero case + twins. Delete when A's code lands."""
from __future__ import annotations

import itertools
import json
from difflib import SequenceMatcher
from pathlib import Path

from artemis.models import (AdjustmentKind, AdjustmentResult, AllocationLine, AllocationResult,
                            ContradictionFlag, CoreError, CoreResult, Evidence, EvidenceRef,
                            EvidenceStatus, Grade, Tier)

TOL = 100  # paise
_STRIP = ("PRIVATE", "PVT", "LIMITED", "LTD", "LLP", "AND", "CO")


def _norm(s: str) -> str:
    words = "".join(c if c.isalnum() else " " for c in s.upper()).split()
    return " ".join(w for w in words if w not in _STRIP)


class FixtureCore:
    def __init__(self, fixtures_dir: str | Path = "fixtures"):
        self.customers, self.invoices, self.receipts, self.emails = {}, {}, {}, {}
        self.tax_credits, self.credit_notes, self.cases = [], [], {}
        for f in sorted(Path(fixtures_dir).glob("case_*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            self.customers.update({c["id"]: c for c in d["customers"]})
            self.invoices.update({i["id"]: i for i in d["invoices"]})
            self.receipts.update({r["utr"]: r for r in d["bank_receipts"]})
            self.emails.update({e["id"]: e for e in d["remittance_emails"]})
            self.tax_credits += d["tax_credits"]
            self.credit_notes += d["credit_notes"]
            self.cases[d["case_id"]] = {"utr": d["utr"], "customer_id": d["customer_id"]}

    # ---- helpers
    def _inv(self, invoice_id: str) -> dict:
        if invoice_id not in self.invoices:
            raise CoreError("not_found", f"invoice {invoice_id} does not exist")
        return self.invoices[invoice_id]

    @staticmethod
    def _ref(kind, tier, table, sid, excerpt="") -> EvidenceRef:
        return EvidenceRef(kind=kind, tier=tier, source_table=table, source_id=sid, excerpt=excerpt)

    # ---- CoreService
    def new_case_ids(self) -> list[str]:
        return sorted(self.cases)

    def reset(self) -> dict:
        return {}

    def auto_close(self) -> list[str]:
        return []

    def save_parsed_email(self, email_id: str, parsed: dict) -> None:
        pass

    def opening_context(self, case_id: str) -> dict:
        if case_id not in self.cases:
            raise CoreError("not_found", f"case {case_id}")
        receipt = self.receipts[self.cases[case_id]["utr"]]
        cands = self.resolve_customer(receipt["payer_name_raw"]).data["candidates"]
        top = cands[0]["customer_id"] if cands else None
        open_inv = [i for i in self.invoices.values() if i["customer_id"] == top and i["status"] == "open"]
        combos = [c for n in (1, 2, 3) for c in itertools.combinations(open_inv, n)]
        best = min(combos, key=lambda c: abs(sum(i["gross_amount"] for i in c) - receipt["amount"]),
                   default=())
        return {"case_id": case_id, "receipt": receipt, "customer_candidates": cands,
                "open_invoices": open_inv,
                "best_combination": {"invoice_ids": [i["id"] for i in best],
                                     "variance_paise": sum(i["gross_amount"] for i in best) - receipt["amount"]}}

    def search_ledger(self, customer_id, amount_paise=None, date_from=None, date_to=None, status=None):
        rows = [i for i in self.invoices.values() if i["customer_id"] == customer_id
                and i["status"] == (status or "open")
                and (amount_paise is None or i["gross_amount"] == amount_paise)
                and (date_from is None or i["invoice_date"] >= date_from)
                and (date_to is None or i["invoice_date"] <= date_to)]
        refs = [self._ref("invoice", Tier.PRIMARY, "invoices", i["id"], f"gross_paise={i['gross_amount']}")
                for i in rows]
        return CoreResult(data={"invoices": rows}, refs=refs)

    def search_bank_receipts(self, customer_id=None, amount_paise=None, date_from=None, date_to=None,
                             narration_text=None):
        rows = [r for r in self.receipts.values()
                if (customer_id is None or r["resolved_customer_id"] == customer_id)
                and (amount_paise is None or r["amount"] == amount_paise)
                and (date_from is None or r["value_date"] >= date_from)
                and (date_to is None or r["value_date"] <= date_to)
                and (narration_text is None or narration_text.lower() in r["narration"].lower())]
        refs = [self._ref("bank_receipt", Tier.PRIMARY, "bank_receipts", r["utr"], f"amount_paise={r['amount']}")
                for r in rows]
        return CoreResult(data={"receipts": rows}, refs=refs)

    def search_remittance_email(self, customer_id=None, utr=None, invoice_ids=None, text=None):
        def hit(e):
            body = e["body_text"]
            return bool((customer_id and e["customer_id"] == customer_id) or (utr and utr in body)
                        or any(i in body for i in invoice_ids or []) or (text and text.lower() in body.lower()))
        rows = [e for e in self.emails.values() if hit(e)]
        out = [{"id": e["id"], "subject": e["subject"], "excerpt": e["body_text"][:160]} for e in rows]
        refs = [self._ref("remittance_email", Tier.SUPPORTING, "remittance_emails", e["id"], e["body_text"][:160])
                for e in rows]
        return CoreResult(data={"emails": out}, refs=refs)

    def get_email(self, email_id):
        if email_id not in self.emails:
            raise CoreError("not_found", f"email {email_id}")
        body = self.emails[email_id]["body_text"]
        return CoreResult(data={"id": email_id, "body_text": body},
                          refs=[self._ref("remittance_email", Tier.SUPPORTING, "remittance_emails",
                                          email_id, body[:160])])

    def get_authorized_tax_credit_extract(self, customer_id, quarter):
        tan = self.customers.get(customer_id, {}).get("tan")
        if tan is None:
            raise CoreError("not_found", f"customer {customer_id}")
        rows = [t for t in self.tax_credits if t["deductor_tan"] == tan and t["quarter"] == quarter]
        refs = [self._ref("tax_credit", Tier.PRIMARY, "tax_credits", t["id"],
                          f"amount_credited_paise={t['amount_credited']}") for t in rows]
        return CoreResult(data={"rows": rows}, refs=refs)

    def compute_withholding(self, customer_id, invoice_ids, transaction_date):
        cust = self.customers.get(customer_id)
        if cust is None:
            raise CoreError("not_found", f"customer {customer_id}")
        base = sum(self._inv(i)["taxable_value"] for i in invoice_ids)
        rate = cust["tds_rate_bp"] if cust["tds_applicable"] else 0
        new_act = transaction_date >= "2026-04-01"
        data = {"expected_paise": (base * rate + 5000) // 10000, "base_paise": base, "rate_bp": rate,
                "rule_ref": "Sec 393, Income-tax Act 2025" if new_act else "Sec 194C, Income-tax Act 1961",
                "rule_version": "2026-04-01" if new_act else "legacy"}
        ref = self._ref("withholding_calc", Tier.DERIVED, "rules", data["rule_version"],
                        f"expected_paise={data['expected_paise']}")
        return CoreResult(data=data, refs=[ref])

    def find_credit_notes(self, customer_id, invoice_ids=None):
        rows = [c for c in self.credit_notes if c["customer_id"] == customer_id
                and (not invoice_ids or c["invoice_id"] in invoice_ids)]
        refs = [self._ref("credit_note", Tier.PRIMARY if c["status"] == "issued" else Tier.SUPPORTING,
                          "credit_notes", c["id"], f"amount_paise={c['amount']}") for c in rows]
        return CoreResult(data={"credit_notes": rows}, refs=refs)

    def resolve_customer(self, name_raw):
        n = _norm(name_raw)
        scored = []
        for c in self.customers.values():
            full = _norm(c["legal_name"])
            ratio = 1.0 if n and full.startswith(n) else SequenceMatcher(None, n, full).ratio()
            scored.append((int(100 * ratio), c))
        scored.sort(key=lambda t: -t[0])
        cands = [{"customer_id": c["id"], "legal_name": c["legal_name"], "score": s}
                 for s, c in scored if s >= 80]
        refs = [self._ref("entity_match", Tier.DERIVED, "customer_aliases",
                          f"{name_raw}->{c['customer_id']}", f"score={c['score']}") for c in cands[:1]]
        return CoreResult(data={"candidates": cands}, refs=refs)

    def propose_allocation(self, case_id, utrs, allocations, adjustments):
        recv = []
        for u in utrs:
            if u not in self.receipts:
                raise CoreError("not_found", f"receipt {u}")
            recv.append(self.receipts[u])
        lines = [AllocationLine(**a) for a in allocations]
        invs = [self._inv(a.invoice_id) for a in lines]
        cust = invs[0]["customer_id"] if invs else None
        invoiced, received = sum(i["gross_amount"] for i in invs), sum(r["amount"] for r in recv)
        variance = invoiced - received
        remaining, results = variance, []
        for adj in sorted(adjustments, key=lambda a: a["kind"] == AdjustmentKind.ROUNDING):  # rounding last
            ok, rule, amt, kind = False, "", adj["amount_paise"], adj["kind"]
            if kind == AdjustmentKind.TDS:
                exp = self.compute_withholding(cust, [i["id"] for i in invs],
                                               recv[0]["value_date"]).data["expected_paise"]
                ok, rule = abs(amt - exp) <= TOL, f"tds==compute_withholding({exp})"
            elif kind == AdjustmentKind.CREDIT_NOTE:
                ids = [i["id"] for i in invs]
                ok = any(c["id"] == adj.get("credit_note_id") and c["customer_id"] == cust
                         and c["amount"] == amt and c["invoice_id"] in ids for c in self.credit_notes)
                rule = "credit note exists for customer+invoice, amount equal"
            elif kind == AdjustmentKind.BANK_CHARGE:
                ok, rule = amt == sum(r["bank_charges"] for r in recv), "equals statement bank_charges"
            elif kind == AdjustmentKind.ROUNDING:
                ok, rule = abs(amt) <= TOL and amt == remaining, "abs<=100 and only remaining gap"
            if ok:
                remaining -= amt
            results.append(AdjustmentResult(**adj, validated=ok, validated_by_rule=rule if ok else ""))
        return AllocationResult(case_id=case_id, utrs=utrs, allocations=lines, adjustments=results,
                                invoiced_paise=invoiced, received_paise=received,
                                variance_paise=variance, unexplained_paise=remaining)

    def grade(self, case_id, allocation, evidence: list[Evidence]) -> Grade:
        if allocation is None:
            return Grade(status=EvidenceStatus.INSUFFICIENT, unexplained_paise=None)
        inv_ids = [a.invoice_id for a in allocation.allocations]
        if any(self.invoices[i]["status"] == "applied" for i in inv_ids):
            return Grade(status=EvidenceStatus.INSUFFICIENT, unexplained_paise=allocation.unexplained_paise,
                         duplicate=True, recommendation="refund_or_hold (controller approval)")
        cust = self.invoices[inv_ids[0]]["customer_id"]
        exp = self.compute_withholding(cust, inv_ids, self.receipts[allocation.utrs[0]]["value_date"]
                                       ).data["expected_paise"]
        calc = next((e for e in evidence if e.kind == "withholding_calc"), None)
        flags: list[ContradictionFlag] = []
        for e in evidence:  # contradiction flag 1 only; Lane A implements all seven
            if e.source_table == "tax_credits" and calc:
                tc = next(t for t in self.tax_credits if t["id"] == e.source_id)
                if abs(tc["amount_credited"] - exp) > TOL:
                    flags.append(ContradictionFlag(
                        code=1, evidence_a=calc.id, evidence_b=e.id,
                        detail=f"tax credit {tc['amount_credited']} vs computed {exp} (paise)"))
        if flags:
            return Grade(status=EvidenceStatus.CONFLICTING, unexplained_paise=allocation.unexplained_paise,
                         flags=flags)
        if abs(allocation.unexplained_paise) > TOL:
            return Grade(status=EvidenceStatus.INSUFFICIENT, unexplained_paise=allocation.unexplained_paise)
        by_id = {e.id: e for e in evidence}
        all_primary = all(any(by_id[i].tier == Tier.PRIMARY for i in a.evidence_ids if i in by_id)
                          for a in allocation.adjustments if a.validated)
        return Grade(status=EvidenceStatus.VERIFIED if all_primary else EvidenceStatus.PROBABLE,
                     unexplained_paise=allocation.unexplained_paise)
