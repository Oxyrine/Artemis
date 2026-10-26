import pytest
from sqlalchemy import select

from artemis.db import CreditNote, Customer, Invoice
from artemis.models import CoreError
from artemis.rules import withholding
from tests.lane_a.conftest import TRUTH, case_with

HERO_ALLOC = [dict(invoice_id="INV-1042", amount_paise=118_000_000), dict(invoice_id="INV-1043", amount_paise=35_400_000)]


# ------------------------------------------------------------------ compute_withholding / TDS rules
def test_hero_case_is_26000_under_the_2025_act(real):
    d = real.core.compute_withholding("CUST-014", ["INV-1042", "INV-1043"], "2026-09-12").data
    assert d == {"expected_paise": 2_600_000, "base_paise": 130_000_000, "rate_bp": 200,
                 "rule_ref": "Sec 393, Income-tax Act 2025", "rule_version": "2026-04-01"}


def test_both_rule_versions_are_selected_by_date(real):
    legacy = real.core.compute_withholding("CUST-014", ["INV-1042"], "2026-03-31").data
    new = real.core.compute_withholding("CUST-014", ["INV-1042"], "2026-04-01").data
    assert legacy["rule_ref"] == "Sec 194C, Income-tax Act 1961" and legacy["rule_version"] == "legacy"
    assert new["rule_ref"] == "Sec 393, Income-tax Act 2025"
    assert legacy["expected_paise"] == new["expected_paise"] == 2_000_000  # 2% of the 10,00,000 taxable value


def test_the_generated_legacy_invoice_uses_the_old_section(real):
    with real.core.db.tx() as s:
        legacy = s.scalars(select(Invoice).where(Invoice.invoice_date < "2026-04-01")).one()  # the one pre-April invoice
    rc = real.core.search_bank_receipts(customer_id=legacy.customer_id).data["receipts"]
    pay = next(r["value_date"] for r in rc if r["value_date"] < "2026-04-01")
    assert real.core.compute_withholding(legacy.customer_id, [legacy.id], pay).data["rule_ref"].startswith("Sec 194C")


def test_not_applicable_customers_and_rounding(real):
    with real.core.db.tx() as s:
        non_tds = s.scalars(select(Customer).where(Customer.tds_applicable.is_(False))).first()
        inv = s.scalars(select(Invoice).where(Invoice.customer_id == non_tds.id)).first()
        assert withholding.compute(non_tds, [inv], "2026-09-12")["expected_paise"] == 0  # only the configured flag decides
        c = s.get(Customer, "CUST-014")
        odd = Invoice(id="X", customer_id="CUST-014", invoice_date="", due_date="", taxable_value=12_345,
                      gst_amount=0, gross_amount=12_345)
        assert withholding.compute(c, [odd], "2026-09-12")["expected_paise"] == 247  # 246.9 paise -> half-up
    with pytest.raises(CoreError):
        withholding.select_rule("nonexistent", "2026-09-12")


# ------------------------------------------------------------------ variance engine: every adjustment row
def prop(core, adjustments, utrs=("UTR839201",), alloc=None, case="CASE-0007"):
    return core.propose_allocation(case, list(utrs), alloc or HERO_ALLOC, adjustments)


def adj(kind, amount, **kw):
    return dict(kind=kind, amount_paise=amount, evidence_ids=[], **kw)


def test_hero_case_closes_to_zero(real):
    r = prop(real.core, [adj("tds", 2_600_000)])
    assert (r.invoiced_paise, r.received_paise, r.variance_paise, r.unexplained_paise) == (153_400_000, 150_800_000,
                                                                                         2_600_000, 0)
    assert r.adjustments[0].validated and "compute_withholding" in r.adjustments[0].validated_by_rule


@pytest.mark.parametrize("amount,validated", [(2_600_000, True), (2_600_100, True), (2_599_900, True),
                                              (2_600_101, False), (2_599_899, False), (2_000_000, False)])
def test_tds_validates_within_100_paise_of_compute_withholding(real, amount, validated):
    r = prop(real.core, [adj("tds", amount)])
    assert r.adjustments[0].validated is validated
    assert (abs(r.unexplained_paise) <= 100) is validated  # only validated adjustments count


def test_unvalidated_adjustments_never_reduce_the_gap(real):
    r = prop(real.core, [adj("tds", 5_000_000)])
    assert r.unexplained_paise == r.variance_paise == 2_600_000


def test_credit_note_rows(real):
    cid = case_with(status="VERIFIED", n_adjustments=2)  # TDS + an ERP-issued credit note on the same receipt
    t = TRUTH[cid]
    inv, utr = t["allocations"][0], t["receipts"][0]
    cn_amt = next(a["amount_paise"] for a in t["adjustments"] if a["kind"] == "credit_note")
    tds = next(a["amount_paise"] for a in t["adjustments"] if a["kind"] == "tds")
    with real.core.db.tx() as s:
        cn = s.scalars(select(CreditNote).where(CreditNote.invoice_id == inv["invoice_id"])).one()
        other = s.scalars(select(CreditNote).where(CreditNote.id != cn.id)).first()
    ok = real.core.propose_allocation(cid, [utr], [inv], [adj("tds", tds), adj("credit_note", cn_amt, credit_note_id=cn.id)])
    assert all(a.validated for a in ok.adjustments) and ok.unexplained_paise == 0  # two adjustments, closes to 0
    for bad in (adj("credit_note", cn_amt + 1, credit_note_id=cn.id),  # amount differs
                adj("credit_note", cn_amt, credit_note_id=other.id),  # a different invoice's credit note
                adj("credit_note", cn_amt, credit_note_id="CN-NOPE"),  # does not exist
                adj("credit_note", cn_amt)):  # no id at all
        r = real.core.propose_allocation(cid, [utr], [inv], [adj("tds", tds), bad])
        assert not r.adjustments[1].validated and r.unexplained_paise == cn_amt


def test_bank_charge_must_equal_the_statement_line(real):
    cid = next(c for c, t in TRUTH.items() if any(a["kind"] == "bank_charge" for a in t["adjustments"]))
    t = TRUTH[cid]
    amt = t["adjustments"][0]["amount_paise"]
    ok = real.core.propose_allocation(cid, t["receipts"], t["allocations"], [adj("bank_charge", amt)])
    assert ok.adjustments[0].validated and ok.unexplained_paise == 0
    bad = real.core.propose_allocation(cid, t["receipts"], t["allocations"], [adj("bank_charge", amt - 1)])
    assert not bad.adjustments[0].validated


def test_rounding_only_when_small_and_the_only_remaining_gap(real):
    cid = next(c for c, t in TRUTH.items() if any(a["kind"] == "rounding" for a in t["adjustments"]))
    t = TRUTH[cid]
    ok = real.core.propose_allocation(cid, t["receipts"], t["allocations"], [adj("rounding", 50)])
    assert ok.adjustments[0].validated and ok.unexplained_paise == 0
    assert not real.core.propose_allocation(cid, t["receipts"], t["allocations"], [adj("rounding", 49)]
                                            ).adjustments[0].validated  # not the whole gap
    # on the hero case a 26,000 gap is never "rounding", and 101 paise is over the limit
    assert not prop(real.core, [adj("rounding", 2_600_000)]).adjustments[0].validated
    assert not prop(real.core, [adj("tds", 2_599_899), adj("rounding", 101)]).adjustments[1].validated
    assert prop(real.core, [adj("tds", 2_599_950), adj("rounding", 50)]).adjustments[1].validated  # rounding judged last


def test_unknown_ids_are_errors_not_guesses(real):
    with pytest.raises(CoreError, match="INV-9999"):
        real.core.propose_allocation("CASE-0007", ["UTR839201"], [dict(invoice_id="INV-9999", amount_paise=1)], [])
    with pytest.raises(CoreError, match="UTR000"):
        real.core.propose_allocation("CASE-0007", ["UTR000"], HERO_ALLOC, [])
    with pytest.raises(CoreError, match="CASE-9999"):
        real.core.propose_allocation("CASE-9999", ["UTR839201"], HERO_ALLOC, [])


def test_the_latest_proposal_replaces_the_previous_one(real):
    prop(real.core, [adj("tds", 2_600_000)])
    prop(real.core, [adj("tds", 2_600_000)])
    from artemis.db import Adjustment, Allocation, Case
    with real.core.db.tx() as s:
        assert len(s.scalars(select(Allocation).where(Allocation.case_id == "CASE-0007")).all()) == 2
        assert len(s.scalars(select(Adjustment).where(Adjustment.case_id == "CASE-0007")).all()) == 1
        assert s.get(Case, "CASE-0007").unexplained_paise == 0


def test_every_answer_key_case_reproduces_its_own_arithmetic(real):
    """Feed each case's answer-key allocations + adjustments to the engine: unexplained must equal variance minus
    the key's adjustments, and every key adjustment must validate (email-only credit notes aside)."""
    checked = 0
    for cid, t in TRUTH.items():
        if not t["allocations"] or t["status"] == "AUTO_CLOSED":
            continue
        adjs = []
        for a in t["adjustments"]:
            d = adj(a["kind"], a["amount_paise"])
            if a["kind"] == "credit_note":
                with real.core.db.tx() as s:
                    cn = s.scalars(select(CreditNote).where(CreditNote.invoice_id == t["allocations"][0]["invoice_id"])).first()
                if cn is None:  # agreed in email only: no ERP row until the email is parsed (see the next test)
                    continue
                d["credit_note_id"] = cn.id
            adjs.append(d)
        r = real.core.propose_allocation(cid, t["receipts"], t["allocations"], adjs)
        assert all(a.validated for a in r.adjustments), (cid, r.adjustments)
        assert r.unexplained_paise == r.variance_paise - sum(a.amount_paise for a in r.adjustments)
        checked += 1
    assert checked >= 28


def test_an_email_only_credit_note_becomes_supporting_evidence_after_parsing(real):
    cid = next(c for c, t in TRUTH.items() if t["status"] == "PROBABLE" and t["adjustments"][0]["kind"] == "credit_note")
    t = TRUTH[cid]
    inv_id, utr = t["allocations"][0]["invoice_id"], t["receipts"][0]
    amt = t["adjustments"][0]["amount_paise"]
    cust = real.core.search_ledger(customer_id=next(i["customer_id"] for i in real.core.search_ledger(
        customer_id=real.core.opening_context(cid)["customer_candidates"][0]["customer_id"]).data["invoices"]
        if i["id"] == inv_id)).data["invoices"][0]["customer_id"]
    assert real.core.find_credit_notes(cust, [inv_id]).data["credit_notes"] == []  # nothing in the ERP
    email = real.core.search_remittance_email(utr=utr).data["emails"][0]["id"]
    parsed = {"invoice_refs": [inv_id], "stated_deductions": [{"kind": "credit note", "amount_paise": amt}]}
    real.core.save_parsed_email(email, parsed)
    real.core.save_parsed_email(email, parsed)  # idempotent
    found = real.core.find_credit_notes(cust, [inv_id])
    (row,) = found.data["credit_notes"]
    assert (row["source"], row["status"]) == ("email_only", "agreed_not_issued")
    assert found.refs[0].tier.value == "supporting"  # never primary: caps the case at PROBABLE
    r = real.core.propose_allocation(cid, [utr], t["allocations"], [adj("credit_note", amt, credit_note_id=row["id"])])
    assert r.adjustments[0].validated and r.unexplained_paise == 0


def test_one_invoice_paid_by_two_receipts_is_counted_once(real):
    cid = next(c for c, t in TRUTH.items() if len(t["receipts"]) == 2)
    t = TRUTH[cid]
    inv = t["allocations"][0]
    with real.core.db.tx() as s:
        gross = s.get(Invoice, inv["invoice_id"]).gross_amount
    half = gross // 2
    # an agent may list the invoice once per receipt; the gross must still count once, and the amounts add up per invoice
    r = real.core.propose_allocation(cid, t["receipts"], [dict(invoice_id=inv["invoice_id"], amount_paise=half),
                                                           dict(invoice_id=inv["invoice_id"], amount_paise=gross - half)], [])
    assert r.invoiced_paise == gross and r.unexplained_paise == 0
    assert [(a.invoice_id, a.amount_paise) for a in r.allocations] == [(inv["invoice_id"], gross)]
