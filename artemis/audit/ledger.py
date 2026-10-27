"""Hash-chained, append-only audit ledger (implements ports.AuditSink).

    hash = SHA-256(prev_hash + canonical_json({seq, case_id, event_type, actor, payload, created_at}))

Canonical JSON = sorted keys, no spaces, UTF-8. The first event's prev_hash is 64 zeros. Appends join the caller's
transaction (Db.tx), so a state change and its audit event commit or roll back together, and take the Db lock (plus a
Postgres advisory lock) so two writers can never fork the chain. Payloads hold references and hashes, never raw
content: long strings are replaced by a short prefix and their SHA-256."""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select, text

from artemis.audit import signing
from artemis.audit.models import AuditCheckpoint, AuditEvent
from artemis.db import Db

GENESIS = "0" * 64
EVENT_TYPES = frozenset({
    # the spec's list
    "BATCH_STARTED", "CASE_CREATED", "AUTO_CLOSED", "INVESTIGATION_STARTED", "HYPOTHESIS_RECORDED", "TOOL_CALLED",
    "ALLOCATION_PROPOSED", "GRADED", "STATE_CHANGED", "EVIDENCE_REQUESTED", "REVIEW_DECIDED", "APPLIED",
    "NARRATIVE_GENERATED", "BATCH_COMPLETED",
    # emitted by the agent runner when an investigation fails
    "INVESTIGATION_FAILED"})
MAX_STR = 200
_ADVISORY_KEY = 7_341_001


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(prev_hash: str, seq: int, case_id, event_type: str, actor: str, payload: dict, created_at: str) -> str:
    body = canonical({"seq": seq, "case_id": case_id, "event_type": event_type, "actor": actor, "payload": payload,
                      "created_at": created_at})
    return hashlib.sha256((prev_hash + body).encode("utf-8")).hexdigest()


def _refs_only(v):
    """Keep references and numbers; shrink long text to a prefix + length + SHA-256 (raw bodies/prompts stay out)."""
    if isinstance(v, str) and len(v) > MAX_STR:
        return f"{v[:120]}…[len={len(v)} sha256={hashlib.sha256(v.encode()).hexdigest()[:16]}]"
    if isinstance(v, dict):
        return {k: _refs_only(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_refs_only(x) for x in v]
    return v


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class SqlAudit:
    def __init__(self, db: Db):
        self.db = db

    def append(self, case_id: str | None, event_type: str, actor: str, payload: dict) -> int:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown audit event type {event_type!r}")
        payload = _refs_only(json.loads(json.dumps(payload, default=str)))  # JSON-safe, then shrunk
        with self.db.tx() as s:
            if s.bind.dialect.name == "postgresql":
                s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_KEY})
            last = s.execute(select(AuditEvent.seq, AuditEvent.hash).order_by(AuditEvent.seq.desc()).limit(1)).first()
            seq, prev = (last.seq + 1, last.hash) if last else (1, GENESIS)
            created = _now()
            s.add(AuditEvent(seq=seq, case_id=case_id, event_type=event_type, actor=actor,
                             payload_json=canonical(payload), prev_hash=prev, created_at=created,
                             hash=_digest(prev, seq, case_id, event_type, actor, payload, created)))
            s.flush()
        return seq

    # ---- reading
    @property
    def events(self) -> list[dict]:
        """Same shape as the in-memory ListAudit, so code and tests written against it work on the real ledger."""
        return [self.as_dict(e) for e in self.rows()]

    @staticmethod
    def as_dict(e: AuditEvent) -> dict:
        return {"seq": e.seq, "case_id": e.case_id, "event_type": e.event_type, "actor": e.actor,
                "payload": json.loads(e.payload_json), "prev_hash": e.prev_hash, "hash": e.hash,
                "created_at": e.created_at}

    def rows(self, case_id: str | None = None, limit: int | None = None) -> list[AuditEvent]:
        with self.db.tx() as s:
            q = select(AuditEvent).order_by(AuditEvent.seq)
            if case_id:
                q = q.where(AuditEvent.case_id == case_id)
            rows = list(s.scalars(q))
            return rows[-limit:] if limit else rows

    # ---- checkpoints: the latest hash, signed, so rewriting the whole chain is detectable too
    def checkpoint(self, batch_id: str | None = None, key: Ed25519PrivateKey | None = None,
                   out_dir: str | Path | None = None) -> dict | None:
        key = key or signing.load_or_create_key()
        with self.db.tx() as s:
            last = s.execute(select(AuditEvent.seq, AuditEvent.hash).order_by(AuditEvent.seq.desc()).limit(1)).first()
            if last is None:
                return None
            body = {"seq": last.seq, "hash": last.hash, "batch_id": batch_id, "created_at": _now()}
            sig = base64.b64encode(key.sign(canonical(body).encode())).decode()
            cp = {**body, "signature": sig, "public_key": signing.public_b64(key), "algorithm": "ed25519"}
            s.add(AuditCheckpoint(seq=last.seq, hash=last.hash, batch_id=batch_id, created_at=body["created_at"],
                                  signature=sig, public_key=cp["public_key"]))
        if out_dir:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            Path(out_dir, f"checkpoint-{cp['seq']:06d}.json").write_text(json.dumps(cp, indent=2), encoding="utf-8")
        return cp

    def latest_checkpoint(self) -> dict | None:
        with self.db.tx() as s:
            cp = s.scalars(select(AuditCheckpoint).order_by(AuditCheckpoint.id.desc()).limit(1)).first()
            if cp is None:
                return None
            return {"seq": cp.seq, "hash": cp.hash, "batch_id": cp.batch_id, "created_at": cp.created_at,
                    "signature": cp.signature, "public_key": cp.public_key, "algorithm": "ed25519"}

    # ---- verification
    def verify(self, key: Ed25519PrivateKey | None = None) -> dict:
        """Recompute every hash in order and check each signed checkpoint against the chain.
        Returns {ok, first_broken_seq, checked, checkpoints, reason}."""
        key = key or signing.load_or_create_key()
        pub = key.public_key()
        broken: list[tuple[int, str]] = []
        with self.db.tx() as s:
            prev, expect, by_seq = GENESIS, 1, {}
            for ev in s.scalars(select(AuditEvent).order_by(AuditEvent.seq)):
                if ev.seq != expect:
                    broken.append((expect, f"event {expect} is missing from the chain"))
                    expect = ev.seq
                payload = json.loads(ev.payload_json)
                if ev.prev_hash != prev or ev.hash != _digest(prev, ev.seq, ev.case_id, ev.event_type, ev.actor,
                                                              payload, ev.created_at):
                    broken.append((ev.seq, f"hash mismatch at event {ev.seq}"))
                    break
                prev, expect = ev.hash, ev.seq + 1
                by_seq[ev.seq] = ev.hash
            checked = len(by_seq)
            cps = list(s.scalars(select(AuditCheckpoint).order_by(AuditCheckpoint.id)))
            for cp in cps:
                body = canonical({"seq": cp.seq, "hash": cp.hash, "batch_id": cp.batch_id, "created_at": cp.created_at})
                try:
                    pub.verify(base64.b64decode(cp.signature), body.encode())
                except InvalidSignature:
                    broken.append((cp.seq, f"checkpoint at {cp.seq} has an invalid signature"))
                    continue
                if by_seq.get(cp.seq) != cp.hash:
                    broken.append((cp.seq, f"chain disagrees with the signed checkpoint at {cp.seq}"))
        first = min(broken, key=lambda b: b[0]) if broken else None
        return {"ok": not broken, "first_broken_seq": first[0] if first else None, "checked": checked,
                "checkpoints": len(cps), "reason": first[1] if first else None}
