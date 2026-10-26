import pytest
from sqlalchemy import select

from artemis.db import Adjustment, Case, TaxCredit
from artemis.models import CaseState as S, Evidence, EvidenceStatus as ES, Tier
from artemis.ports import IllegalTransition
from artemis.grading.policy import TRANSITIONS
from tests.lane_a.conftest import TRUTH, case_with, evidence

ALLOC = [dict(invoice_id="INV-1042", amount_paise=118_000_000), dict(invoice_id="INV-1043", amount_paise=35_400_000)]


class Hero:
    """CASE-0007 plus the pieces an agent would gather, with real evidence ids."""

    def __init__(self, real, case="CASE-0007", cust="CUST-014", utr="UTR839201", invs=("INV-1042", "INV-1043")):
        c = real.core
        self.real, self.case, self.cust, self.utr = real, case, cust, utr
        self.calc = c.compute_withholding(cust, list(invs), "2026-09-12")
        self.tax = c.get_authorized_tax_credit_extract(cust, 2)
        self.mail = c.search_remittance_email(utr=utr)
        self.rcpt = c.search_bank_receipts(customer_id=cust)
        self.inv = c.search_ledger(cust)
        self.alloc = [dict(invoice_id=i, amount_paise=a["gross_amount"]) for i in invs
                      for a in self.inv.data["invoices"] if a["id"] == i]

    def grade(self, *results, cite=None, tds=2_600_000, adjustments=None):
        ev = evidence(self.case, *results)
        ids = cite if cite is not None else [e.id for e in ev if e.kind in ("withholding_calc", "tax_credit")]
        adjs = adjustments if adjustments is not None else [dict(kind="tds", amount_paise=tds, evidence_ids=ids)]
        alloc = self.real.core.propose_allocation(self.case, [self.utr], self.alloc, adjs)
        return self.real.core.grade(self.case, alloc, ev)


def codes(g):
    return sorted(f.code for f in g.flags)


# ------------------------------------------------------------------ the four statuses
def test_verified_needs_unexplained_zero_and_primary_evidence(real):
    h = Hero(real)
    g = h.grade(h.calc, h.tax)
    assert g.status == ES.VERIFIED and g.flags == [] and g.unexplained_paise == 0
    with real.core.db.tx() as s:
        assert s.get(Case, "CASE-0007").evidence_status == "VERIFIED"  # the grade is persisted on the case


def test_probable_when_an_adjustment_rests_only_on_supporting_evidence(real):
    h = Hero(real, "CASE-0008", "CUST-015", "UTR839202", ("INV-1052", "INV-1053"))
    assert h.tax.data["rows"] == []  # the tax credit is not filed yet
    g = h.grade(h.calc, h.mail)
    assert g.status == ES.PROBABLE and g.unexplained_paise == 0


def test_a_primary_item_of_the_wrong_kind_does_not_make_it_verified(real):
    h = Hero(real)
    ev = evidence("CASE-0007", h.calc, h.inv)  # invoice evidence is primary, but it cannot support a TDS adjustment
    ids = [e.id for e in ev if e.kind in ("withholding_calc", "invoice")]
    alloc = real.core.propose_allocation("CASE-0007", ["UTR839201"], ALLOC, [dict(kind="tds", amount_paise=2_600_000,
                                                                                 evidence_ids=ids)])
    assert real.core.grade("CASE-0007", alloc, ev).status == ES.PROBABLE


def test_insufficient_when_the_gap_is_not_closed_or_nothing_was_proposed(real):
    h = Hero(real)
    assert h.grade(h.calc, adjustments=[]).status == ES.INSUFFICIENT
    assert real.core.grade("CASE-0007", None, []).status == ES.INSUFFICIENT


def test_conflicting_whatever_the_variance(real):
    h = Hero(real, "CASE-0009", "CUST-016", "UTR839203", ("INV-1062", "INV-1063"))
    assert h.tax.data["rows"][0]["amount_credited"] == 2_000_000  # shows 20,000 against the computed 26,000
    g = h.grade(h.calc, h.tax)
    assert g.status == ES.CONFLICTING and g.unexplained_paise == 0 and codes(g) == [1]
    assert {g.flags[0].evidence_a, g.flags[0].evidence_b} == {"EV-0001", "EV-0002"}  # the two disagreeing items


def test_the_grader_finds_a_contradiction_the_agent_never_fetched(real):
    h = Hero(real, "CASE-0009", "CUST-016", "UTR839203", ("INV-1062", "INV-1063"))
    g = h.grade(h.calc)  # the agent skipped the tax-credit extract entirely
    assert g.status == ES.CONFLICTING and codes(g) == [1] and g.flags[0].evidence_b.startswith("tax_credits:TC-")


# ------------------------------------------------------------------ the seven contradiction flags, each alone
def test_flag_2_deductor_is_not_the_customer(real):
    h = Hero(real)
    with real.core.db.tx() as s:
        stray = s.scalars(select(TaxCredit).where(TaxCredit.deductor_tan.like("DELX%"))).first().id
    stray_ev = Evidence(id="EV-9", case_id="CASE-0007", kind="tax_credit", tier=Tier.PRIMARY,
                        source_table="tax_credits", source_id=stray)
    ev = evidence("CASE-0007", h.calc, h.tax) + [stray_ev]
    alloc = real.core.propose_allocation("CASE-0007", ["UTR839201"], ALLOC, [dict(kind="tds", amount_paise=2_600_000,
                                         evidence_ids=["EV-0001", "EV-0002"])])
    g = real.core.grade("CASE-0007", alloc, ev)
    assert g.status == ES.CONFLICTING and codes(g) == [2]


def parse(real, utr, parsed):
    real.core.save_parsed_email(real.core.search_remittance_email(utr=utr).data["emails"][0]["id"], parsed)


def test_flag_3_email_states_a_different_deduction(real):
    h = Hero(real)
    parse(real, "UTR839201", {"stated_deductions": [{"kind": "tds", "amount_paise": 3_000_000}], "claimed_utrs": ["UTR839201"]})
    g = h.grade(h.calc, h.tax, h.mail)
    assert codes(g) == [3] and g.status == ES.CONFLICTING


def test_flag_6_email_and_erp_disagree_on_an_invoice_amount(real):
    h = Hero(real)
    parse(real, "UTR839201", {"invoice_amounts": [{"invoice_ref": "INV-1042", "amount_paise": 117_000_000}]})
    assert codes(h.grade(h.calc, h.tax, h.mail)) == [6]


def test_flag_5_email_credit_note_differs_from_the_erp_one(real):
    cid = case_with(status="VERIFIED", n_adjustments=2)
    t = TRUTH[cid]
    inv, utr = t["allocations"][0]["invoice_id"], t["receipts"][0]
    cust = real.core.opening_context(cid)["customer_candidates"][0]["customer_id"]
    cn = real.core.find_credit_notes(cust, [inv])
    cn_id, cn_amt = cn.data["credit_notes"][0]["id"], cn.data["credit_notes"][0]["amount"]
    tds = next(a["amount_paise"] for a in t["adjustments"] if a["kind"] == "tds")
    parse(real, utr, {"stated_deductions": [{"kind": "credit_note", "amount_paise": cn_amt + 50_000}]})
    ev = evidence(cid, cn, real.core.search_remittance_email(utr=utr))
    alloc = real.core.propose_allocation(cid, [utr], t["allocations"], [
        dict(kind="tds", amount_paise=tds, evidence_ids=[]), dict(kind="credit_note", amount_paise=cn_amt,
                                                                   credit_note_id=cn_id, evidence_ids=[ev[0].id])])
    g = real.core.grade(cid, alloc, ev)
    assert codes(g) == [5] and g.status == ES.CONFLICTING


def test_flag_4_narration_cites_another_customers_invoice(real):
    cid = next(c for c, t in TRUTH.items() if t["allocations"] and t["allocations"][0]["invoice_id"] == "INV-2210")
    t = TRUTH[cid]
    alloc = real.core.propose_allocation(cid, t["receipts"], t["allocations"], [])
    g = real.core.grade(cid, alloc, evidence(cid, real.core.search_bank_receipts(narration_text="INV-2201")))
    assert codes(g) == [4] and g.status == ES.CONFLICTING and g.unexplained_paise == 0
    assert g.flags[0].evidence_a.startswith("EV-") and g.flags[0].evidence_b == "invoices:INV-2201"


def test_flag_7_email_claims_a_payment_with_no_bank_receipt(real):
    cid = next(c for c, t in TRUTH.items() if t["status"] == "CONFLICTING" and t["is_red_team"] and not t["adjustments"]
               and t["allocations"][0]["invoice_id"] != "INV-2210")
    t = TRUTH[cid]
    utr = t["receipts"][0]
    email_id = real.core.search_remittance_email(utr=utr).data["emails"][0]["id"]
    body = real.core.get_email(email_id).data["body_text"]
    ghost = next(w.strip(".,:") for w in body.split() if w.startswith("UTR") and w.strip(".,:") != utr)
    parse(real, utr, {"claimed_utrs": [utr, ghost]})
    alloc = real.core.propose_allocation(cid, t["receipts"], t["allocations"], [])
    g = real.core.grade(cid, alloc, evidence(cid, real.core.search_remittance_email(utr=utr)))
    assert codes(g) == [7] and g.flags[0].evidence_b == f"bank_receipts:{ghost}"


def test_clean_cases_raise_no_flags(real):
    h = Hero(real)
    parse(real, "UTR839201", {"stated_deductions": [{"kind": "tds", "amount_paise": 2_600_000}], "claimed_utrs": ["UTR839201"],
                              "invoice_amounts": [{"invoice_ref": "INV-1042", "amount_paise": 118_000_000}]})
    g = h.grade(h.calc, h.tax, h.mail)
    assert g.flags == [] and g.status == ES.VERIFIED  # an agreeing email changes nothing


def test_duplicate_payment_is_insufficient_with_a_controller_only_refund(real):
    cid = next(c for c, t in TRUTH.items() if t["status"] == "INSUFFICIENT" and t["is_red_team"])
    g = real.core.grade(cid, None, [])
    assert g.status == ES.INSUFFICIENT and g.duplicate and "controller" in g.recommendation
    with real.core.db.tx() as s:
        assert s.get(Case, cid).duplicate is True
    plain = next(c for c, t in TRUTH.items() if t["status"] == "INSUFFICIENT" and not t["is_red_team"])
    assert real.core.grade(plain, None, []).duplicate is False


# ------------------------------------------------------------------ policy: every illegal transition is refused
def set_state(real, case_id, state):  # test setup only: the policy engine is the one writer in production
    with real.core.db.tx() as s:
        s.get(Case, case_id).state = state.value


@pytest.mark.parametrize("frm", list(S))
def test_transition_table_is_enforced_for_every_pair(real, frm):
    for to in S:
        set_state(real, "CASE-0007", frm)
        before = len(real.audit.events)
        if to in TRANSITIONS.get(frm, set()):
            real.policy.transition("CASE-0007", to, "agent")
            assert real.policy.state_of("CASE-0007") == to
            last = real.audit.events[-1]
            assert (last["event_type"], last["payload"]) == ("STATE_CHANGED", {"from": frm.value, "to": to.value})
        else:
            with pytest.raises(IllegalTransition):
                real.policy.transition("CASE-0007", to, "agent")
            assert real.policy.state_of("CASE-0007") == frm and len(real.audit.events) == before  # no event on refusal


def test_applied_is_reachable_only_through_pending_approval():
    assert [f.value for f, tos in TRANSITIONS.items() if S.APPLIED in tos] == ["PENDING_APPROVAL"]


# ------------------------------------------------------------------ policy: what a reviewer may do
def pending(real, booked=2_600_000, duplicate=False):
    set_state(real, "CASE-0007", S.PENDING_APPROVAL)
    with real.core.db.tx() as s:
        for old in s.scalars(select(Adjustment).where(Adjustment.case_id == "CASE-0007")):
            s.delete(old)
        s.add(Adjustment(case_id="CASE-0007", kind="tds", amount_paise=booked, validated=True))
        s.get(Case, "CASE-0007").duplicate = duplicate


def test_analyst_approves_the_hero_case_within_the_limit(real):
    pending(real)  # 15,08,000 received, but only 26,000 booked: inside the analyst's 10,00,000 limit
    assert real.policy.decide("CASE-0007", "analyst-1", "approve") == S.APPLIED
    assert real.policy.state_of("CASE-0007") == S.APPLIED
    assert real.audit.events[-1]["actor"] == "reviewer:analyst-1"


def test_approving_above_the_analysts_limit_needs_a_controller(real):
    pending(real, booked=10_00_001 * 100)
    with pytest.raises(IllegalTransition, match="approval limit"):
        real.policy.decide("CASE-0007", "analyst-1", "approve")
    assert real.policy.state_of("CASE-0007") == S.PENDING_APPROVAL  # refused, nothing changed
    assert real.policy.decide("CASE-0007", "controller-1", "approve") == S.APPLIED


def test_duplicate_refund_recommendations_need_a_controller(real):
    pending(real, duplicate=True)
    with pytest.raises(IllegalTransition, match="controller"):
        real.policy.decide("CASE-0007", "analyst-1", "approve")
    assert real.policy.decide("CASE-0007", "controller-1", "approve") == S.APPLIED


def test_probable_and_conflicting_cases_cannot_be_approved(real):
    set_state(real, "CASE-0008", S.AWAITING_EVIDENCE)
    with pytest.raises(IllegalTransition, match="Probable"):
        real.policy.decide("CASE-0008", "controller-1", "approve")
    set_state(real, "CASE-0009", S.NEEDS_REVIEW)
    with pytest.raises(IllegalTransition, match="nobody approves"):
        real.policy.decide("CASE-0009", "controller-1", "approve")


def test_reject_and_request_evidence_and_bad_inputs(real):
    pending(real)
    assert real.policy.decide("CASE-0007", "analyst-1", "request_evidence") == S.AWAITING_EVIDENCE
    pending(real)
    assert real.policy.decide("CASE-0007", "analyst-1", "reject") == S.REJECTED
    pending(real)
    for who, what in (("nobody", "approve"), ("analyst-1", "shrug")):
        with pytest.raises(IllegalTransition):
            real.policy.decide("CASE-0007", who, what)
    with pytest.raises(IllegalTransition, match="unknown case"):
        real.policy.transition("CASE-9999", S.INVESTIGATING, "agent")


def test_allocating_a_duplicate_onto_the_applied_invoice_never_clears(real):
    """The agent may propose the receipt against the already-applied invoice; that must not read as a clean match."""
    cid = next(c for c, t in TRUTH.items() if t["status"] == "INSUFFICIENT" and t["is_red_team"])
    utr = TRUTH[cid]["receipts"][0]
    cust = real.core.opening_context(cid)["customer_candidates"][0]["customer_id"]
    inv = real.core.search_ledger(cust, status="applied").data["invoices"][0]
    alloc = real.core.propose_allocation(cid, [utr], [dict(invoice_id=inv["id"], amount_paise=inv["gross_amount"])], [])
    assert alloc.unexplained_paise == 0  # arithmetically it closes...
    g = real.core.grade(cid, alloc, [])
    assert g.status == ES.INSUFFICIENT and g.duplicate  # ...but it is a duplicate, never VERIFIED
