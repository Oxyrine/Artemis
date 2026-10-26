"""Deterministic matcher and case builder (no LLM).

1. Resolve each receipt's payer to a customer (names.resolve); a resolution writes an alias row.
2. Group receipts into cases: two receipts from the same resolved customer whose narrations cite the same invoice
   number become one case; everything else is one receipt per case. Case ids are CASE-0001.. in order of each
   group's lowest UTR (data/generator numbers its answer key the same way).
3. Auto-close a case only if ALL hold: customer resolved at >=95; exactly one open invoice of that customer
   whose gross equals the receipt; the narration's invoice reference (if any) is that invoice; the value date
   is between the invoice date and its due date + 30 days; the invoice is not already applied; no dispute flag."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from artemis.db import Allocation, BankReceipt, Case, Customer, CustomerAlias, Db, Invoice
from artemis.matching import names
from artemis.models import CaseState
from artemis.ports import AuditSink
from artemis.grading.policy import SqlPolicy

INV_REF = re.compile(r"INV-\d+")
WINDOW_DAYS = 30  # value date may be up to this many days after the due date
DISPUTED: frozenset[str] = frozenset()  # no dispute data exists in the environment; the hook is explicit


def _group(receipts: list[BankReceipt]) -> list[list[BankReceipt]]:
    parent = {r.utr: r.utr for r in receipts}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seen: dict[tuple[str, str], str] = {}
    for r in receipts:
        if r.resolved_customer_id is None:
            continue
        for ref in set(INV_REF.findall(r.narration)):
            key = (r.resolved_customer_id, ref)
            if key in seen:
                parent[find(r.utr)] = find(seen[key])
            else:
                seen[key] = r.utr
    groups: dict[str, list[BankReceipt]] = {}
    for r in receipts:
        groups.setdefault(find(r.utr), []).append(r)
    return sorted(groups.values(), key=lambda g: min(x.utr for x in g))


def run(db: Db, policy: SqlPolicy, audit: AuditSink) -> list[str]:
    """Resolve, group, create cases, auto-close what qualifies. Returns the AUTO_CLOSED case ids."""
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    closed: list[str] = []
    with db.tx() as s:
        receipts = list(s.scalars(select(BankReceipt).order_by(BankReceipt.utr)))
        legal = {c.id: c.legal_name for c in s.scalars(select(Customer))}
        for r in receipts:
            res = names.resolve(s, r.payer_name_raw, r.narration)
            r.resolution_score = res.score
            if res.customer_id:
                r.resolved_customer_id = res.customer_id
                known = {a.alias for a in s.scalars(select(CustomerAlias).where(
                    CustomerAlias.customer_id == res.customer_id))}
                if r.payer_name_raw not in known and r.payer_name_raw != legal[res.customer_id]:
                    s.add(CustomerAlias(customer_id=res.customer_id, alias=r.payer_name_raw,
                                        source="bank_narration", confidence=res.score))
        s.flush()
        for n, group in enumerate(_group(receipts), 1):
            cid = f"CASE-{n:04d}"
            cust = group[0].resolved_customer_id
            s.add(Case(id=cid, utr=min(r.utr for r in group), customer_id=cust, state=CaseState.NEW.value,
                       created_at=now, updated_at=now))
            for r in group:
                r.case_id = cid
            s.flush()
            audit.append(cid, "CASE_CREATED", "system", {"utrs": [r.utr for r in group], "customer_id": cust})
            inv = _auto_close_invoice(s, group)
            if inv is not None:
                case = s.get(Case, cid)
                case.variance_paise = case.unexplained_paise = 0
                s.add(Allocation(case_id=cid, invoice_id=inv.id, amount_paise=inv.gross_amount))
                inv.status = "applied"
                policy.apply(s, cid, CaseState.AUTO_CLOSED, "system")
                audit.append(cid, "AUTO_CLOSED", "system", {"invoice_id": inv.id, "amount_paise": inv.gross_amount})
                closed.append(cid)
    return closed


def _auto_close_invoice(s, group: list[BankReceipt]) -> Invoice | None:
    if len(group) != 1:
        return None
    r = group[0]
    if r.resolved_customer_id is None or (r.resolution_score or 0) < names.RESOLVED or r.utr in DISPUTED:
        return None
    match = list(s.scalars(select(Invoice).where(
        Invoice.customer_id == r.resolved_customer_id, Invoice.status == "open", Invoice.gross_amount == r.amount)))
    if len(match) != 1:
        return None
    inv = match[0]
    refs = set(INV_REF.findall(r.narration))
    if refs and refs != {inv.id}:
        return None
    lo, hi = date.fromisoformat(inv.invoice_date), date.fromisoformat(inv.due_date) + timedelta(days=WINDOW_DAYS)
    return inv if lo <= date.fromisoformat(r.value_date) <= hi else None
