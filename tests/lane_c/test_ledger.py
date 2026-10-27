import hashlib
import json
import threading

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from artemis.audit.ledger import GENESIS, canonical
from artemis.audit.models import AuditEvent, drop_trigger_statements, install_triggers
from artemis.audit.tamper import tamper
from artemis.db import Db
from tests.lane_c.conftest import fill


def as_owner(db: Db, *sql: str):
    """What the database owner can do and the application cannot: drop the guard, change rows, put the guard back."""
    with db.lock, db.engine.begin() as c:
        for q in drop_trigger_statements("audit_events", c.dialect.name):
            c.exec_driver_sql(q)
        for q in sql:
            c.exec_driver_sql(q)
        install_triggers(c, "audit_events")


def test_empty_and_filled_chains_verify(ledger, key):
    assert ledger.verify(key)["ok"] and ledger.checkpoint(key=key) is None  # nothing to checkpoint yet
    fill(ledger)
    assert ledger.verify(key) == {"ok": True, "first_broken_seq": None, "checked": 5, "checkpoints": 0, "reason": None}


def test_the_hash_is_exactly_the_specified_formula(ledger):
    fill(ledger, 2)
    first, second = ledger.rows()
    body = lambda e: canonical({"seq": e.seq, "case_id": e.case_id, "event_type": e.event_type, "actor": e.actor,  # noqa: E731
                                "payload": json.loads(e.payload_json), "created_at": e.created_at})
    assert first.prev_hash == GENESIS == "0" * 64  # the first event chains from 64 zeros
    assert first.hash == hashlib.sha256((GENESIS + body(first)).encode("utf-8")).hexdigest()
    assert second.prev_hash == first.hash
    assert body(first) == canonical(json.loads(body(first)))  # sorted keys, no spaces
    assert " " not in body(first).replace(first.actor, "").replace(first.event_type, "").replace(first.created_at, "")


def test_editing_one_event_is_reported_at_that_seq(ledger, key):
    fill(ledger, 6)
    ledger.checkpoint(key=key)
    as_owner(ledger.db, """UPDATE audit_events SET payload_json = '{"status":"VERIFIED","unexplained_paise":999}' WHERE seq = 3""")
    v = ledger.verify(key)
    assert v["ok"] is False and v["first_broken_seq"] == 3 and "hash mismatch" in v["reason"]


def test_a_deleted_event_is_detected(ledger, key):
    fill(ledger, 5)
    as_owner(ledger.db, "DELETE FROM audit_events WHERE seq = 2")
    v = ledger.verify(key)
    assert v["ok"] is False and v["first_broken_seq"] == 2 and "missing" in v["reason"]


def test_rewriting_the_whole_chain_is_caught_by_the_signed_checkpoint(ledger, key):
    fill(ledger, 5)
    ledger.checkpoint(key=key)
    # a forger who owns the database edits event 2 and recomputes EVERY hash so the chain is self-consistent...
    rows = ledger.rows()
    prev, updates = GENESIS, []
    for e in rows:
        payload = {"status": "VERIFIED", "unexplained_paise": 777} if e.seq == 2 else json.loads(e.payload_json)
        from artemis.audit.ledger import _digest
        h = _digest(prev, e.seq, e.case_id, e.event_type, e.actor, payload, e.created_at)
        updates.append(f"UPDATE audit_events SET payload_json = '{canonical(payload)}', prev_hash = '{prev}', hash = '{h}' "
                       f"WHERE seq = {e.seq}")
        prev = h
    as_owner(ledger.db, *updates)
    v = ledger.verify(key)  # ...the chain alone looks fine, but the signed checkpoint still pins the old hash
    assert v["ok"] is False and "signed checkpoint" in v["reason"] and v["first_broken_seq"] == 5


def test_a_checkpoint_signed_with_another_key_is_rejected(ledger, key):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    fill(ledger, 3)
    ledger.checkpoint(key=Ed25519PrivateKey.generate())  # forged by someone without the server's key
    v = ledger.verify(key)
    assert v["ok"] is False and "invalid signature" in v["reason"]


def test_checkpoint_export_is_a_signed_json_file(ledger, key, tmp_path):
    fill(ledger, 3)
    cp = ledger.checkpoint("BATCH-0001", key=key, out_dir=tmp_path)
    saved = json.loads(next(tmp_path.glob("checkpoint-*.json")).read_text(encoding="utf-8"))
    assert saved == cp and cp["seq"] == 3 and cp["batch_id"] == "BATCH-0001" and cp["algorithm"] == "ed25519"
    assert ledger.latest_checkpoint()["hash"] == cp["hash"] and ledger.verify(key)["ok"]


def test_updates_and_deletes_are_refused_by_the_database(ledger):
    fill(ledger, 2)
    with pytest.raises(DatabaseError, match="append-only"):
        with ledger.db.tx() as s:
            s.execute(text("UPDATE audit_events SET actor = 'x' WHERE seq = 1"))
    with pytest.raises(DatabaseError, match="append-only"):
        with ledger.db.tx() as s:
            s.execute(text("DELETE FROM audit_events"))
    assert len(ledger.rows()) == 2


def test_concurrent_writers_never_fork_the_chain(ledger, key):
    def work(t):
        for i in range(25):
            ledger.append(f"CASE-{t:04d}", "TOOL_CALLED", "agent", {"i": i})
    threads = [threading.Thread(target=work, args=(t,)) for t in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    rows = ledger.rows()
    assert [r.seq for r in rows] == list(range(1, 201)) and ledger.verify(key)["ok"]


def test_an_audit_event_commits_or_rolls_back_with_the_state_change(real):
    before_events, before_state = len(real.audit.events), real.policy.state_of("CASE-0007")
    with pytest.raises(RuntimeError):
        with real.core.db.tx():
            real.policy.transition("CASE-0007", __import__("artemis.models", fromlist=["CaseState"]).CaseState.INVESTIGATING, "agent")
            raise RuntimeError("the request failed after the state change")
    assert real.policy.state_of("CASE-0007") == before_state and len(real.audit.events) == before_events  # neither stuck


def test_payloads_keep_references_not_raw_content(ledger):
    ledger.append("CASE-0001", "EVIDENCE_REQUESTED", "agent", {"what": "x" * 5000, "ids": ["EV-0001"], "n": 3})
    p = json.loads(ledger.rows()[0].payload_json)
    assert len(p["what"]) < 200 and "sha256=" in p["what"] and p["ids"] == ["EV-0001"] and p["n"] == 3


def test_unknown_event_types_are_rejected(ledger):
    with pytest.raises(ValueError, match="unknown audit event type"):
        ledger.append(None, "SOMETHING_ELSE", "system", {})


def test_the_tamper_script_breaks_the_chain_at_the_edited_event(real, key):
    real.audit.checkpoint(key=key)
    assert real.audit.verify(key)["ok"]
    hit = tamper(real.core.db)
    v = real.audit.verify(key)
    assert v["ok"] is False and v["first_broken_seq"] == hit["seq"] and hit["after"] == hit["before"] + 100_000
