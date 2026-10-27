"""Builds the API's view-models from Lane A's database (cases, receipts, invoices, allocations) and Lane B's run records
(evidence, tool calls, outcomes). Read-only: nothing here changes a case."""
from __future__ import annotations

import re

from sqlalchemy import select

from artemis.api.views import (ActionState, AdjustmentView, AllocationView, CaseDetail, CaseList, CaseSummary,
                               ClosureLine, EvidenceGraph, EvidenceView, FlagSide, FlagView, GradeView, GraphEdge,
                               GraphNode, InvoiceView, ProposedEntry, ReceiptView, ReviewerActions, RunInfo, RupeeSummary,
                               VarianceClosure)
from artemis.db import Adjustment, Allocation, BankReceipt, Case, CreditNote, Customer, Invoice, Reviewer, TaxCredit
from artemis.models import CaseState, Tier
from artemis.money import format_inr
from artemis.ports import IllegalTransition

STATUSES = ("AUTO_CLOSED", "VERIFIED", "PROBABLE", "INSUFFICIENT", "CONFLICTING")
ACCOUNTS = {"tds": "TDS receivable", "credit_note": "Credit notes", "bank_charge": "Bank charges",
            "rounding": "Rounding difference"}  # where an approved adjustment is booked
_AMOUNT = re.compile(r"(?:paise|amount_credited_paise|expected_paise)=(-?\d+)")


def _status(case: Case) -> str | None:
    return "AUTO_CLOSED" if case.state == CaseState.AUTO_CLOSED.value else case.evidence_status


# ------------------------------------------------------------------ dashboard
def case_list(deps, status: str | None = None, state: str | None = None) -> CaseList:
    store = deps.store
    outcomes = {o.case_id: o for o in store.outcomes()}
    with deps.core.db.tx() as s:
        cust = {c.id: c.legal_name for c in s.scalars(select(Customer))}
        receipts: dict[str, list[BankReceipt]] = {}
        for r in s.scalars(select(BankReceipt).order_by(BankReceipt.utr)):
            receipts.setdefault(r.case_id, []).append(r)
        rows = []
        for c in s.scalars(select(Case).order_by(Case.id)):
            o = outcomes.get(c.id)
            rows.append(CaseSummary(
                case_id=c.id, utrs=[r.utr for r in receipts.get(c.id, [])], customer_id=c.customer_id,
                customer_name=cust.get(c.customer_id), receipt_paise=sum(r.amount for r in receipts.get(c.id, [])),
                variance_paise=c.variance_paise, unexplained_paise=c.unexplained_paise, status=_status(c),
                state=CaseState(c.state), steps=store.get_run(o.run_id).steps if o else None, duplicate=c.duplicate))
    counts = {k: sum(r.status == k for r in rows) for k in STATUSES}
    var = lambda r: r.variance_paise or 0  # noqa: E731
    rupees = RupeeSummary(
        investigated_variance_paise=sum(var(r) for r in rows if r.status in STATUSES[1:]),
        explained_verified_paise=sum(var(r) - (r.unexplained_paise or 0) for r in rows if r.status == "VERIFIED"),
        held_paise=sum(var(r) for r in rows if r.status in ("PROBABLE", "INSUFFICIENT", "CONFLICTING")))
    shown = [r for r in rows if (not status or r.status == status) and (not state or r.state.value == state)]
    return CaseList(total=len(rows), counts_by_status=counts, rupees=rupees, cases=shown)


# ------------------------------------------------------------------ case detail
def _tool_names(deps, case_id: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for run in deps.store.runs(case_id):
        for tc in deps.store.tool_calls(run.replay_of or run.id):
            names[tc.id] = tc.tool_name
    return names


def _side(s, ref: str, ev_by_id: dict) -> FlagSide:
    """One side of a contradiction: an evidence item the agent retrieved, or a 'table:id' the grader found itself."""
    if ref in ev_by_id:
        e = ev_by_id[ref]
        table, sid, kind, excerpt = e.source_table, e.source_id, e.kind, e.excerpt
    else:
        table, _, sid = ref.partition(":")
        kind = {"tax_credits": "tax_credit", "invoices": "invoice", "bank_receipts": "bank_receipt",
                "credit_notes": "credit_note", "customers": "customer", "rules": "withholding_calc"}.get(table, table)
        excerpt = ""
    amount = None
    if table == "tax_credits" and (tc := s.get(TaxCredit, sid)):
        amount, excerpt = tc.amount_credited, excerpt or f"{tc.deductor_name} ({tc.deductor_tan}), {tc.transaction_date}"
    elif table == "invoices" and (inv := s.get(Invoice, sid)):
        amount, excerpt = inv.gross_amount, excerpt or f"{inv.id} of {inv.customer_id}"
    elif table == "bank_receipts" and (r := s.get(BankReceipt, sid)):
        amount, excerpt = r.amount, excerpt or r.narration
    elif table == "credit_notes" and (cn := s.get(CreditNote, sid)):
        amount, excerpt = cn.amount, excerpt or f"{cn.id} ({cn.source}, {cn.status})"
    elif table == "customers" and (cu := s.get(Customer, sid)):
        excerpt = excerpt or cu.legal_name
    elif table == "rules":
        m = _AMOUNT.search(excerpt) or re.search(r"(-?\d+)$", sid)
        amount = int(m.group(1)) if m else None
    return FlagSide(ref=ref, kind=kind, excerpt=excerpt, amount_paise=amount)


def detail(deps, case_id: str) -> CaseDetail:
    store, policy = deps.store, deps.policy
    outcome = next((o for o in store.outcomes() if o.case_id == case_id), None)
    with deps.core.db.tx() as s:
        case = s.get(Case, case_id)
        if case is None:
            raise KeyError(case_id)
        cust = s.get(Customer, case.customer_id) if case.customer_id else None
        rcpts = list(s.scalars(select(BankReceipt).where(BankReceipt.case_id == case_id).order_by(BankReceipt.utr)))
        allocs = list(s.scalars(select(Allocation).where(Allocation.case_id == case_id).order_by(Allocation.id)))
        invs = [s.get(Invoice, a.invoice_id) for a in allocs]
        adjs = list(s.scalars(select(Adjustment).where(Adjustment.case_id == case_id).order_by(Adjustment.id)))
        tools = _tool_names(deps, case_id)
        evidence = store.evidence(case_id)
        ev_by_id = {e.id: e for e in evidence}

        flags = [FlagView(code=f.code, detail=f.detail, a=_side(s, f.evidence_a, ev_by_id), b=_side(s, f.evidence_b, ev_by_id))
                 for f in (outcome.grade.flags if outcome and outcome.grade else [])]
        grade = GradeView(status=_status(case), flags=flags, duplicate=case.duplicate,
                          recommendation=outcome.grade.recommendation if outcome and outcome.grade else None)

        closure = None
        if allocs:
            invoiced = sum(i.gross_amount for i in invs)
            validated = [a for a in adjs if a.validated]
            received = sum(r.amount for r in rcpts)
            expected = invoiced - sum(a.amount_paise for a in validated)
            closure = VarianceClosure(
                invoiced_paise=invoiced, adjustments=[ClosureLine(kind=a.kind, amount_paise=a.amount_paise,
                                                                  validated=a.validated) for a in adjs],
                expected_paise=expected, received_paise=received, unexplained_paise=expected - received)

        entries = [ProposedEntry(kind="allocation", invoice_id=a.invoice_id, account=None, amount_paise=a.amount_paise)
                   for a in allocs]
        entries += [ProposedEntry(kind="adjustment", invoice_id=None, account=ACCOUNTS.get(a.kind, a.kind),
                                  amount_paise=a.amount_paise) for a in adjs if a.validated]

        narrative, source = (outcome.narrative, outcome.narrative_source) if outcome else (None, None)
        if outcome is None and case.state == CaseState.AUTO_CLOSED.value and allocs:
            narrative, source = (f"Exact match: receipt {rcpts[0].utr} of INR {format_inr(rcpts[0].amount)} equals "
                                 f"{allocs[0].invoice_id}; closed automatically by the matcher.", "template")
        run = None
        if outcome:
            r = store.get_run(outcome.run_id)
            run = RunInfo(run_id=r.id, model=r.model, prompt_version=r.prompt_version,
                          stop_reason=r.stop_reason.value if r.stop_reason else None, steps=r.steps,
                          replay=bool(r.replay_of))

        actions = []
        for rv in s.scalars(select(Reviewer).order_by(Reviewer.id)):
            states = {}
            for d in ("approve", "request_evidence", "reject"):
                try:
                    policy.check_review(s, case_id, rv.id, d)
                    states[d] = ActionState(allowed=True, reason=None)
                except IllegalTransition as e:
                    states[d] = ActionState(allowed=False, reason=e.reason)
            actions.append(ReviewerActions(reviewer_id=rv.id, name=rv.name, role=rv.role, **states))

        return CaseDetail(
            case_id=case_id, state=CaseState(case.state), status=_status(case), customer_id=case.customer_id,
            customer_name=cust.legal_name if cust else None,
            receipts=[ReceiptView(utr=r.utr, value_date=r.value_date, amount_paise=r.amount,
                                  payer_name_raw=r.payer_name_raw, narration=r.narration, bank_charges_paise=r.bank_charges,
                                  resolution_score=r.resolution_score) for r in rcpts],
            invoices=[InvoiceView(id=i.id, invoice_date=i.invoice_date, due_date=i.due_date, taxable_paise=i.taxable_value,
                                  gst_paise=i.gst_amount, gross_paise=i.gross_amount, status=i.status) for i in invs],
            allocations=[AllocationView(invoice_id=a.invoice_id, amount_paise=a.amount_paise) for a in allocs],
            adjustments=[AdjustmentView(kind=a.kind, amount_paise=a.amount_paise, validated=a.validated,
                                        validated_by_rule=a.validated_by_rule, evidence_ids=a.evidence_ids or [])
                         for a in adjs],
            evidence=[EvidenceView(id=e.id, kind=e.kind, tier=e.tier, source_table=e.source_table, source_id=e.source_id,
                                   excerpt=e.excerpt, tool_call_id=e.retrieved_by_tool_call_id,
                                   tool_name=tools.get(e.retrieved_by_tool_call_id or "")) for e in evidence],
            grade=grade, closure=closure, proposed_entries=entries, narrative=narrative, narrative_source=source,
            run=run, actions=actions)


# ------------------------------------------------------------------ evidence graph
def graph(deps, case_id: str) -> EvidenceGraph:
    """Nodes and edges only, no positions: the browser lays the graph out (dagre), so a UI redesign never touches this."""
    d = detail(deps, case_id)
    ev = {e.id: e for e in d.evidence}
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def node(n: GraphNode) -> str:
        nodes.setdefault(n.id, n)
        return n.id

    def edge(src: str, dst: str, kind: str, label: str | None = None, amount: int | None = None) -> None:
        edges.append(GraphEdge(id=f"e{len(edges) + 1}", source=src, target=dst, kind=kind, label=label, amount_paise=amount))

    one_invoice = len(d.allocations) == 1
    for r in d.receipts:
        node(GraphNode(id=f"rcpt:{r.utr}", kind="receipt", label=r.utr, tier=Tier.PRIMARY, amount_paise=r.amount_paise))
    for a in d.allocations:
        node(GraphNode(id=f"inv:{a.invoice_id}", kind="invoice", label=a.invoice_id, tier=Tier.PRIMARY,
                       amount_paise=a.amount_paise))
        for r in d.receipts:
            edge(f"rcpt:{r.utr}", f"inv:{a.invoice_id}", "allocates",
                 amount=r.amount_paise if one_invoice else (a.amount_paise if len(d.receipts) == 1 else None))
    adj_ids: dict[str, str] = {}
    flagged = {r for f in d.grade.flags for r in (f.a.ref, f.b.ref)}  # an item that contradicts cannot also "support"
    for i, a in enumerate(d.adjustments):
        aid = node(GraphNode(id=f"adj:{i}", kind="adjustment", label=a.kind, amount_paise=a.amount_paise,
                             validated=a.validated))
        adj_ids.setdefault(a.kind, aid)
        for inv in d.allocations:
            edge(aid, f"inv:{inv.invoice_id}", "adjusts")
        for eid in a.evidence_ids:
            if eid not in ev:
                continue
            e = ev[eid]
            if e.kind == "withholding_calc":  # the calculation hangs off a rule node, and is never the dissenter
                rule = node(GraphNode(id=f"rule:{e.source_id}", kind="rule", label=e.excerpt or e.source_id))
                edge(rule, aid, "rule", label=e.source_id)
            elif eid not in flagged:
                edge(node(GraphNode(id=eid, kind="evidence", label=e.kind, tier=e.tier)), aid, "supports")
    def side_node(side: FlagSide) -> str:
        return node(GraphNode(id=side.ref, kind="evidence", label=side.kind,
                              tier=ev[side.ref].tier if side.ref in ev else None, amount_paise=side.amount_paise))

    for f in d.grade.flags:  # contradictions: the item that disagrees points at the adjustment it undermines
        kind, culprit = {1: ("tds", f.b), 2: ("tds", f.a), 3: ("tds", f.a), 5: ("credit_note", f.a)}.get(f.code, (None, None))
        if kind in adj_ids:
            edge(side_node(culprit), adj_ids[kind], "contradicts", label=f"flag {f.code}")
        else:  # no adjustment to point at (e.g. a narration citing someone else's invoice): join the two sides directly
            edge(side_node(f.a), side_node(f.b), "contradicts", label=f"flag {f.code}")
    return EvidenceGraph(case_id=case_id, nodes=list(nodes.values()), edges=edges)
