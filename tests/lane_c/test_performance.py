"""Guards for the speed work: each of these was measured to matter on a hosted Postgres."""
import asyncio
import threading

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from artemis.agent.batch import run_batch
from artemis.agent.llm import ScriptedLLM
from artemis.api.app import create_app
from artemis.audit.models import AuditEvent
from artemis.db import Case, Db
from artemis.fakes.scripted import golden_agent
from artemis.tools import registry
from artemis.wiring import build_deps
from tests.conftest import HERO


def test_tool_schemas_are_generated_once_and_still_match_the_input_models():
    first = registry.schemas()
    assert registry.schemas() is first  # the loop asks on every step: regenerating twelve schemas each time cost a third of a batch
    fresh = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                               "parameters": registry._slim(t.input.model_json_schema())}} for t in registry.TOOLS.values()]
    assert first == fresh  # cached, not stale: still generated from the Pydantic models


def test_reset_empties_every_table_including_the_append_only_ledger():
    deps = build_deps("real")
    asyncio.run(run_batch(deps, lambda c: ScriptedLLM(golden_agent(deps.core, c)), case_ids=HERO))
    with deps.core.db.tx() as s:
        assert s.scalar(select(func.count()).select_from(AuditEvent)) > 0
    deps.core.reset()
    with deps.core.db.tx() as s:
        assert s.scalar(select(func.count()).select_from(AuditEvent)) == 0  # a TRUNCATE must not miss the ledger's tables
    deps.core.auto_close()
    assert deps.audit.verify()["ok"] and deps.audit.rows()[0].seq == 1  # a fresh chain from genesis


def test_the_db_lock_serialises_sqlite_but_never_a_server_database():
    db = Db()
    if db.engine.dialect.name == "sqlite":
        assert isinstance(db.lock, type(threading.RLock()))  # one connection: threads must take turns
    else:
        assert not isinstance(db.lock, type(threading.RLock()))  # a pool: threads overlap while one waits on the network


def test_responses_are_gzipped_when_the_client_accepts_it(tmp_path):
    c = TestClient(create_app(build_deps("real"), runs_dir=tmp_path / "r", exports_dir=tmp_path / "e", static_dir=tmp_path / "none"))
    big = c.get("/api/audit", headers={"Accept-Encoding": "gzip"})
    assert big.status_code == 200 and big.headers.get("content-encoding") == "gzip"
    assert c.get("/api/health", headers={"Accept-Encoding": "gzip"}).headers.get("content-encoding") is None  # tiny: not worth it


def test_the_audit_list_can_be_limited_to_the_newest_events(tmp_path):
    c = TestClient(create_app(build_deps("real"), runs_dir=tmp_path / "r", exports_dir=tmp_path / "e", static_dir=tmp_path / "none"))
    everything = c.get("/api/audit").json()["events"]
    newest = c.get("/api/audit", params={"limit": 5}).json()["events"]
    assert len(everything) > 5 and [e["seq"] for e in newest] == [e["seq"] for e in everything[-5:]]
