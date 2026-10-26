import pytest
from sqlalchemy import select

from artemis.db import Allocation, BankReceipt, Invoice
from artemis.matching import matcher, names
from artemis.models import CaseState
from tests.lane_a.conftest import TRUTH

# (payer string as the bank prints it, narration, expected customer or None, band: certain | high | medium | none)
PAIRS = [
    ("ABC INFRA PVT L", "", "CUST-014", "high"),  # the spec's truncated example
    ("ABC INFRA PRIVATE LIMITED", "", "CUST-014", "high"),
    ("abc infra pvt ltd.", "", "CUST-014", "high"),  # case + punctuation
    ("SUNRISE TEXTILES PVT LTD", "", "CUST-001", "high"),
    ("SUNRISE TEXTILE", "", "CUST-001", "high"),  # truncated inside a word
    ("BHARAT LOGISTICS LTD", "", "CUST-002", "high"),
    ("KAVERI AGRO FOODS", "", "CUST-003", "high"),
    ("LOTUS PHARMA PVT L", "", "CUST-005", "high"),
    ("GANGA POLYMERS LLP", "", "CUST-006", "high"),
    ("ZENITH ELECTRICALS", "", "CUST-007", "high"),
    ("ORCHID HOSPITALITY", "", "CUST-008", "high"),
    ("COASTAL MARINE SERVICES", "", "CUST-010", "high"),
    ("VERTEX SOFTWARE", "", "CUST-011", "high"),
    ("PINNACLE CEMENT CO", "", "CUST-012", "high"),
    ("DELTA BUILD WORKS", "", "CUST-015", "high"),
    ("METRO STEEL INDS", "", "CUST-004", "high"),  # abbreviation expanded: INDS -> INDUSTRIES
    ("METRO STEEL INDUSTRY", "", None, "medium"),  # 80-94: handed to the agent as a candidate
    ("HIMALAYA PAPER MFG", "", None, "medium"),
    ("SOME RANDOM TRADERS", "", None, "none"),  # < 80: unresolved
    ("UNKNOWN PAYER", "NEFT/UTR1/27AAACO0014K1Z5/INV-1", "CUST-014", "certain"),  # GSTIN in the narration = 100
]


@pytest.mark.parametrize("payer,narration,want,band", PAIRS)
def test_entity_resolution(raw, payer, narration, want, band):
    with raw.core.db.tx() as s:  # raw = no learned aliases yet
        r = names.resolve(s, payer, narration)
    assert r.customer_id == want
    if band == "certain":
        assert r.score == 100 and r.via == "gstin"
    elif band == "high":
        assert r.score >= names.RESOLVED
    elif band == "medium":
        assert names.CANDIDATE <= r.score < names.RESOLVED and r.candidates  # candidates for the agent
    else:
        assert r.score < names.CANDIDATE and not r.candidates


def test_pan_in_narration_is_a_certain_match(raw):
    with raw.core.db.tx() as s:
        r = names.resolve(s, "???", "IMPS/UTR9/AAACO0014K")  # PAN of CUST-014
    assert (r.customer_id, r.score, r.via) == ("CUST-014", 100, "pan")


def test_normalize_name():
    assert names.normalize_name("ABC Infra Pvt. Ltd & Co") == "ABC INFRA"
    assert names.normalize_name("  metro   steel inds ") == "METRO STEEL INDUSTRIES"


def test_matcher_auto_closes_exactly_the_ten_expected_cases(real):
    want = sorted(k for k, t in TRUTH.items() if t["status"] == "AUTO_CLOSED")
    states = {c: real.policy.state_of(c) for c in TRUTH}
    got = sorted(c for c, st in states.items() if st == CaseState.AUTO_CLOSED)
    assert got == want and len(got) == 10
    assert all(st == CaseState.NEW for c, st in states.items() if c not in want)  # nothing else was touched
    with real.core.db.tx() as s:
        for c in want:  # allocation written, invoice applied
            a = s.scalars(select(Allocation).where(Allocation.case_id == c)).one()
            assert s.get(Invoice, a.invoice_id).status == "applied"


def test_cases_are_grouped_exactly_as_the_answer_key(real):
    with real.core.db.tx() as s:
        got: dict[str, list[str]] = {}
        for r in s.scalars(select(BankReceipt)):
            got.setdefault(r.case_id, []).append(r.utr)
    assert {k: sorted(v) for k, v in got.items()} == {k: sorted(t["receipts"]) for k, t in TRUTH.items()}


def _first_auto_case(raw):
    with raw.core.db.tx() as s:
        r = s.scalars(select(BankReceipt).where(BankReceipt.utr == "UTR839195")).one()
        return r.utr


@pytest.mark.parametrize("tamper", ["wrong_invoice_ref", "outside_window", "already_applied", "amount_off",
                                    "low_confidence"])
def test_each_auto_close_condition_is_required(raw, tamper):
    """Break one condition of an otherwise-exact match: the matcher must refuse to auto-close it."""
    with raw.core.db.tx() as s:
        r = s.get(BankReceipt, "UTR839195")
        inv = s.get(Invoice, r.narration.split("/")[-1])
        if tamper == "wrong_invoice_ref":
            r.narration += "/INV-1042"
        elif tamper == "outside_window":
            r.value_date = "2026-12-31"
        elif tamper == "already_applied":
            inv.status = "applied"
        elif tamper == "amount_off":
            r.amount += 1
        elif tamper == "low_confidence":
            r.payer_name_raw = "ZZZ HOLDINGS"
    closed = matcher.run(raw.core.db, raw.policy, raw.audit)
    assert "CASE-0001" not in closed and len(closed) == 9
