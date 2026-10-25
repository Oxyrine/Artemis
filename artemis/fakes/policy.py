from __future__ import annotations

from artemis.models import CaseState as S
from artemis.ports import AuditSink, IllegalTransition

_OK: dict[S, set[S]] = {
    S.NEW: {S.AUTO_CLOSED, S.INVESTIGATING, S.MERGED},
    S.INVESTIGATING: {S.GRADED, S.NEEDS_REVIEW},
    S.GRADED: {S.PENDING_APPROVAL, S.AWAITING_EVIDENCE, S.NEEDS_REVIEW},
    S.PENDING_APPROVAL: {S.APPLIED, S.AWAITING_EVIDENCE, S.REJECTED},
    S.AWAITING_EVIDENCE: {S.INVESTIGATING},
    S.NEEDS_REVIEW: {S.INVESTIGATING},  # only via a fresh investigation
}


class FakePolicy:
    def __init__(self, audit: AuditSink, initial: dict[str, S] | None = None):
        self._audit, self._state = audit, dict(initial or {})

    def state_of(self, case_id: str) -> S:
        return self._state.get(case_id, S.NEW)

    def transition(self, case_id: str, to_state: S, actor: str) -> None:
        cur = self.state_of(case_id)
        if to_state not in _OK.get(cur, set()):
            raise IllegalTransition(f"{cur} -> {to_state} is not allowed")
        self._state[case_id] = to_state
        self._audit.append(case_id, "STATE_CHANGED", actor, {"from": cur, "to": to_state})
