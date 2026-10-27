"""Tamper demo: edit one audit event as the database OWNER (who can drop the append-only trigger), then put the trigger
back. GET /audit/verify then reports the break at that seq. Used live in the demo (scripts/tamper.py)."""
from __future__ import annotations

import json

from sqlalchemy import select, text

from artemis.audit.models import AuditEvent, drop_trigger_statements, install_triggers
from artemis.db import Db


def tamper(db: Db, seq: int | None = None) -> dict:
    """Change one amount in an event's payload (default: the first event that carries one). Returns what changed."""
    with db.lock, db.engine.begin() as conn:
        dialect = conn.dialect.name
        rows = conn.execute(select(AuditEvent.seq, AuditEvent.payload_json).order_by(AuditEvent.seq)).all()
        pick = next((r for r in rows if (r.seq == seq if seq else any(k.endswith("_paise") for k in json.loads(r.payload_json)))), None)
        if pick is None:
            raise LookupError("no audit event to tamper with: run a batch first")
        payload = json.loads(pick.payload_json)
        key = next(k for k in payload if k.endswith("_paise")) if seq is None else next(iter(payload), None)
        before = payload.get(key)
        payload[key] = (before + 100_000) if isinstance(before, int) else "tampered"  # +₹1,000 in paise
        for sql in drop_trigger_statements("audit_events", dialect):
            conn.exec_driver_sql(sql)
        conn.execute(text("UPDATE audit_events SET payload_json = :p WHERE seq = :s"),
                     {"p": json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False), "s": pick.seq})
        install_triggers(conn, "audit_events")
    return {"seq": pick.seq, "field": key, "before": before, "after": payload[key]}
