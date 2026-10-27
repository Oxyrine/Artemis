import pytest
from sqlalchemy import select

from artemis.db import BankReceipt, Case
from artemis.models import CaseState as S, CoreError

from tests.lane_a.conftest import TRUTH


def new_cases(real, n):
    """The first n NEW cases that hold a single receipt each."""
    with real.core.db.tx() as s:
        out = []
        for cid in real.core.new_case_ids():
            rs = list(s.scalars(select(BankReceipt.utr).where(BankReceipt.case_id == cid)))
            if len(rs) == 1:
                out.append((cid, rs[0]))
        return out[:n]


def propose(real, case_id, utrs):
    return real.core.propose_allocation(case_id, utrs, [], [])


def test_a_receipt_linked_from_another_new_case_merges_that_case(real):
    (a, ua), (b, ub) = new_cases(real, 2)
    propose(real, a, [ua, ub])
    with real.core.db.tx() as s:
        assert s.get(BankReceipt, ub).case_id == a
        assert s.get(Case, b).merged_into == a
    assert real.policy.state_of(b) == S.MERGED and real.policy.state_of(a) == S.NEW
    assert any(e["case_id"] == b and e["event_type"] == "STATE_CHANGED" and e["payload"]["to"] == "MERGED"
               for e in real.audit.events), "the merge is an audited state change"


def test_a_merged_case_never_comes_back_through_a_new_batch(real):
    (a, ua), (b, ub) = new_cases(real, 2)
    propose(real, a, [ua, ub])
    assert b not in real.core.new_case_ids()


def test_a_receipt_from_a_case_that_is_not_new_is_a_conflict_not_a_merge(real):
    (a, ua), = new_cases(real, 1)
    closed = next(cid for cid, t in TRUTH.items() if t["state"] == "AUTO_CLOSED")
    with real.core.db.tx() as s:
        utr = s.scalars(select(BankReceipt.utr).where(BankReceipt.case_id == closed)).first()
    with pytest.raises(CoreError, match="has not been investigated"):
        propose(real, a, [ua, utr])
    assert real.policy.state_of(closed) == S.AUTO_CLOSED
    with real.core.db.tx() as s:
        assert s.get(BankReceipt, utr).case_id == closed


def test_the_donor_stays_when_it_keeps_other_receipts(real):
    two = [cid for cid, t in TRUTH.items() if len(t["receipts"]) == 2 and t["status"] != "AUTO_CLOSED"][0]
    (a, ua), = new_cases(real, 1)
    with real.core.db.tx() as s:
        first = s.scalars(select(BankReceipt.utr).where(BankReceipt.case_id == two).order_by(BankReceipt.utr)).first()
    propose(real, a, [ua, first])
    assert real.policy.state_of(two) == S.NEW  # still holds its other receipt
