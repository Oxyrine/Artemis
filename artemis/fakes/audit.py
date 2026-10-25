from __future__ import annotations


class ListAudit:
    """Stand-in for Lane C's hash-chained ledger: remembers events, no hashing."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def append(self, case_id, event_type, actor, payload) -> None:
        self.events.append({"seq": len(self.events) + 1, "case_id": case_id,
                            "event_type": event_type, "actor": actor, "payload": payload})
