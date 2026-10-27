import asyncio
import time

from fastapi.testclient import TestClient

from artemis.agent.batch import run_batch
from artemis.agent.llm import ScriptedLLM
from artemis.api.app import create_app
from artemis.fakes.scripted import golden_agent
from artemis.fakes.store import InMemoryRunStore
from artemis.wiring import build_deps
from tests.conftest import HERO


def test_a_run_store_survives_a_round_trip_through_a_dict():
    deps = build_deps("real")
    asyncio.run(run_batch(deps, lambda c: ScriptedLLM(golden_agent(deps.core, c)), case_ids=HERO))
    again = InMemoryRunStore.from_dict(deps.store.to_dict())
    assert again.to_dict() == deps.store.to_dict()
    assert again.next_id("RUN") not in {r.id for r in deps.store.runs()}  # id counters resume past what was recorded


def wait(c, bid):
    for _ in range(360):
        if not c.get(f"/api/batch/{bid}").json()["running"]:
            return
        time.sleep(0.25)
    raise AssertionError("batch did not finish")


def test_traces_and_metrics_survive_a_restart_of_the_server(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'host.db'}")
    first = TestClient(create_app(build_deps("real"), runs_dir=tmp_path / "runs", exports_dir=tmp_path / "exports",
                                  static_dir=tmp_path / "no-ui"))
    wait(first, first.post("/api/batch/run", json={"mode": "demo"}).json()["batch_id"])
    assert first.get("/api/cases/CASE-0007/trace").status_code == 200

    # a restart: new process state, same database, no reseed (what the hosted copy does: ARTEMIS_PREPARE=0)
    second = TestClient(create_app(build_deps("real", prepare=False), runs_dir=tmp_path / "other-runs",
                                   exports_dir=tmp_path / "exports", static_dir=tmp_path / "no-ui"))
    assert second.get("/api/cases/CASE-0007/trace").status_code == 200
    assert second.get("/api/cases/CASE-0007").json()["run"] is not None
    assert second.get("/api/metrics").json()["runs"] > 0
    assert second.post("/api/batch/run", json={"mode": "demo"}).json()["error"] == "nothing_to_do"  # consistent, not a dead end

    # reset starts clean: the old records must not come back on the next restart
    assert second.post("/api/reset").status_code == 200
    third = TestClient(create_app(build_deps("real", prepare=False), runs_dir=tmp_path / "other-runs",
                                  exports_dir=tmp_path / "exports", static_dir=tmp_path / "no-ui"))
    assert third.get("/api/metrics").json()["runs"] == 0
    assert third.get("/api/cases/CASE-0007/trace").status_code == 404
