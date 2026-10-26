"""The ONLY code allowed to change cases.state. Holds the transition table, refuses illegal moves, and calls the
audit sink on every move. Also decides what a named reviewer may do (approval limits, Probable/Conflicting
blocks) and returns the reason the UI shows when an action is blocked."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from artemis.db import Adjustment, Case, Db, Reviewer
from artemis.models import CaseState as S
from artemis.ports import AuditSink, IllegalTransition

TRANSITIONS: dict[S, set[S]] = {
    S.NEW: {S.AUTO_CLOSED, S.INVESTIGATING, S.MERGED},
    S.INVESTIGATING: {S.GRADED, S.NEEDS_REVIEW},
    S.GRADED: {S.PENDING_APPROVAL, S.AWAITING_EVIDENCE, S.NEEDS_REVIEW},
    S.PENDING_APPROVAL: {S.APPLIED, S.AWAITING_EVIDENCE, S.REJECTED},
    S.AWAITING_EVIDENCE: {S.INVESTIGATING},  # back to INVESTIGATING when evidence arrives
    S.NEEDS_REVIEW: {S.INVESTIGATING},  # never APPLIED without a fresh investigation
}
_DECISION_TO_STATE = {"approve": S.APPLIED, "reject": S.REJECTED, "request_evidence": S.AWAITING_EVIDENCE}
_BLOCKED = {  # state -> reason shown beside a disabled button
    S.AWAITING_EVIDENCE: "Probable: waiting for the missing evidence (e.g. the TDS certificate).",
    S.NEEDS_REVIEW: "Insufficient or Conflicting: nobody approves until new evidence re-runs the case.",
    S.APPLIED: "Already applied.", S.REJECTED: "Already rejected.", S.AUTO_CLOSED: "Auto-closed by the matcher.",
    S.NEW: "Not investigated yet.", S.INVESTIGATING: "Investigation in progress.", S.GRADED: "Grading in progress.",
    S.MERGED: "Merged into another case.",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class SqlPolicy:
    def __init__(self, db: Db, audit: AuditSink):
        self._db, self._audit = db, audit

    def state_of(self, case_id: str) -> S:
        with self._db.tx() as s:
            return S(self._case(s, case_id).state)

    def transition(self, case_id: str, to_state: S, actor: str) -> None:
        with self._db.tx() as s:
            self.apply(s, case_id, to_state, actor)

    def apply(self, s: Session, case_id: str, to_state: S, actor: str) -> None:
        """Transition inside the caller's transaction (matcher and API need the move to commit with their writes)."""
        case = self._case(s, case_id)
        cur = S(case.state)
        if to_state not in TRANSITIONS.get(cur, set()):
            raise IllegalTransition(f"{cur.value} -> {to_state.value} is not allowed")
        case.state, case.updated_at = to_state.value, _now()
        self._audit.append(case_id, "STATE_CHANGED", actor, {"from": cur.value, "to": to_state.value})

    def check_review(self, s: Session, case_id: str, reviewer_id: str, decision: str) -> S:
        """Validate a reviewer's decision and return the state it leads to; raises IllegalTransition(reason)."""
        if decision not in _DECISION_TO_STATE:
            raise IllegalTransition(f"unknown decision {decision!r}")
        case, reviewer = self._case(s, case_id), s.get(Reviewer, reviewer_id)
        if reviewer is None:
            raise IllegalTransition(f"unknown reviewer {reviewer_id!r}")
        cur = S(case.state)
        if cur != S.PENDING_APPROVAL:
            raise IllegalTransition(_BLOCKED.get(cur, f"cannot {decision} a case in {cur.value}"))
        if decision == "approve":
            # The limit applies to what the approval books as adjustments (e.g. the 26,000 TDS on the hero case), not to
            # the cash received: the spec has the analyst approve the 15,08,000 hero case under a 10,00,000 limit.
            booked = s.scalar(select(func.sum(Adjustment.amount_paise)).where(
                Adjustment.case_id == case_id, Adjustment.validated.is_(True))) or 0
            limit = reviewer.approval_limit_paise
            if limit is not None and booked > limit:
                raise IllegalTransition(f"Above {reviewer.name}'s approval limit: a controller must approve this.")
            if case.duplicate and reviewer.role != "controller":
                raise IllegalTransition("Duplicate-payment refund recommendations need a controller.")
        return _DECISION_TO_STATE[decision]

    def decide(self, case_id: str, reviewer_id: str, decision: str) -> S:
        """check_review + the transition, atomically. The API route also applies allocations in the same tx."""
        with self._db.tx() as s:
            to = self.check_review(s, case_id, reviewer_id, decision)
            self.apply(s, case_id, to, f"reviewer:{reviewer_id}")
            return to

    @staticmethod
    def _case(s: Session, case_id: str) -> Case:
        case = s.get(Case, case_id)
        if case is None:
            raise IllegalTransition(f"unknown case {case_id}")
        return case
