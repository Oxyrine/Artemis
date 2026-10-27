import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from artemis.agent.batch import run_batch
from artemis.agent.llm import ScriptedLLM
from artemis.api.app import create_app
from artemis.api.views import AuditList, CaseDetail, CaseList, EvidenceGraph, Modes, ReviewResult, VerifyResult
from artemis.db import Adjustment, Invoice
from artemis.fakes.scripted import golden_agent
from artemis.views import BatchStatus, MetricsReport, TraceView
from artemis.wiring import build_deps
from tests.conftest import HERO

ANALYST, CONTROLLER = {"X-Reviewer-Id": "analyst-1"}, {"X-Reviewer-Id": "controller-1"}


def investigated(tmp_path, cases=HERO):
    deps = build_deps("real")
    asyncio.run(run_batch(deps, lambda c: ScriptedLLM(golden_agent(deps.core, c)), case_ids=cases))
    nodist = tmp_path / "no-ui-build"  # tests must not depend on whether web/dist happens to be built
    return TestClient(create_app(deps, runs_dir=tmp_path / "runs", exports_dir=tmp_path / "exports", static_dir=nodist)), deps


@pytest.fixture
def trio(tmp_path):
    return investigated(tmp_path)


def wait(client, bid, seconds=90):
    for _ in range(seconds * 4):
        b = client.get(f"/api/batch/{bid}").json()
        if not b["running"]:
            return b
        time.sleep(0.25)
    raise AssertionError("batch did not finish")


# ------------------------------------------------------------------ batch + modes (one full demo run, then replay)
def test_demo_batch_then_replay_reproduces_it(tmp_path):
    c = TestClient(create_app(build_deps("real"), runs_dir=tmp_path / "runs", exports_dir=tmp_path / "exports",
                              static_dir=tmp_path / "no-ui-build"))
    modes = {m["mode"]: m for m in Modes.model_validate(c.get("/api/modes").json()).model_dump()["modes"]}
    assert modes["demo"]["available"] and not modes["replay"]["available"] and not modes["live"]["available"]
    assert c.post("/api/batch/run", json={"mode": "replay"}).status_code == 409  # nothing recorded yet
    assert c.post("/api/batch/run", json={"mode": "live"}).json()["error"] == "no_llm_key"

    started = c.post("/api/batch/run", json={"mode": "demo"})
    assert started.status_code == 202 and started.json()["mode"] == "demo"
    done = BatchStatus.model_validate(wait(c, started.json()["batch_id"]))
    assert done.counts_by_status == {"VERIFIED": 16, "PROBABLE": 6, "CONFLICTING": 4, "INSUFFICIENT": 4}
    assert done.mode == "demo" and not done.replay and done.done == done.total == 30
    lst = CaseList.model_validate(c.get("/api/cases").json())
    assert lst.counts_by_status == {"AUTO_CLOSED": 10, "VERIFIED": 16, "PROBABLE": 6, "INSUFFICIENT": 4, "CONFLICTING": 4}
    assert c.post("/api/batch/run", json={"mode": "demo"}).json()["error"] == "nothing_to_do"  # all processed
    assert VerifyResult.model_validate(c.get("/api/audit/verify").json()).ok  # sealed with a signed checkpoint
    assert c.get("/api/audit/checkpoint").json()["algorithm"] == "ed25519"

    assert c.get("/api/modes").json()["modes"][1]["available"]  # the demo run left a recording
    again = c.post("/api/batch/run", json={"mode": "replay"})
    replayed = BatchStatus.model_validate(wait(c, again.json()["batch_id"]))
    assert replayed.replay and replayed.mode == "replay"
    assert replayed.counts_by_status == done.counts_by_status and replayed.counts_by_state == done.counts_by_state
    assert c.get("/api/cases/CASE-0007/trace").json()["replay"] is True  # the UI shows the replay badge
    assert c.get("/api/audit/verify").json()["ok"]


# ------------------------------------------------------------------ reads validate against the shared models
def test_every_read_route_matches_its_model(trio):
    c, _ = trio
    for cid in HERO:
        CaseDetail.model_validate(c.get(f"/api/cases/{cid}").json())
        EvidenceGraph.model_validate(c.get(f"/api/cases/{cid}/graph").json())
        TraceView.model_validate(c.get(f"/api/cases/{cid}/trace").json())
    AuditList.model_validate(c.get("/api/audit", params={"case_id": "CASE-0007"}).json())
    MetricsReport.model_validate(c.get("/api/metrics").json())
    assert [r["id"] for r in c.get("/api/reviewers").json()] == ["analyst-1", "controller-1"]
    assert c.get("/api/cases/CASE-9999").status_code == 404 and c.get("/api/batch/BATCH-9999").status_code == 404
    assert c.get("/api/cases/CASE-0001/trace").json()["error"] == "not_found"  # auto-closed: no agent run


def test_hero_detail_closes_to_zero_and_lists_evidence(trio):
    c, _ = trio
    d = CaseDetail.model_validate(c.get("/api/cases/CASE-0007").json())
    assert d.status == "VERIFIED" and d.state.value == "PENDING_APPROVAL" and d.customer_name == "ABC Infra Private Limited"
    z = d.closure
    assert (z.invoiced_paise, z.expected_paise, z.received_paise, z.unexplained_paise) == (153_400_000, 150_800_000,
                                                                                         150_800_000, 0)
    assert [(a.kind, a.amount_paise, a.validated) for a in d.adjustments] == [("tds", 2_600_000, True)]
    assert {e.tier.value for e in d.evidence} >= {"primary", "derived"} and any(e.tool_name for e in d.evidence)
    assert [(e.kind, e.account, e.amount_paise) for e in d.proposed_entries if e.kind == "adjustment"] == [
        ("adjustment", "TDS receivable", 2_600_000)]
    assert d.narrative_source == "template" and "Sec 393" in d.narrative and d.run.steps > 0 and not d.run.replay
    assert all(a.approve.allowed for a in d.actions)  # both reviewers may approve the hero case


def test_conflicting_twin_shows_both_sides_of_the_contradiction(trio):
    c, _ = trio
    d = CaseDetail.model_validate(c.get("/api/cases/CASE-0009").json())
    (flag,) = d.grade.flags
    assert d.status == "CONFLICTING" and flag.code == 1
    assert {flag.a.amount_paise, flag.b.amount_paise} == {2_600_000, 2_000_000}  # computed 26,000 vs credited 20,000
    assert not any(a.approve.allowed for a in d.actions) and "nobody approves" in d.actions[0].approve.reason


def test_evidence_graph_topology(trio):
    c, _ = trio
    g = EvidenceGraph.model_validate(c.get("/api/cases/CASE-0007/graph").json())
    assert {n.kind for n in g.nodes} == {"receipt", "invoice", "adjustment", "rule", "evidence"}
    edge = lambda k: [e for e in g.edges if e.kind == k]  # noqa: E731
    assert len(edge("allocates")) == 2 and len(edge("adjusts")) == 2 and len(edge("rule")) == 1
    assert [e.kind for e in g.edges if e.target == "adj:0" and e.source.startswith("EV-")] == ["supports"]
    assert next(n for n in g.nodes if n.kind == "evidence").tier.value == "primary"  # tax-credit row => solid border
    g9 = EvidenceGraph.model_validate(c.get("/api/cases/CASE-0009/graph").json())
    assert [e.kind for e in g9.edges if e.source.startswith("EV-")] == ["contradicts"]  # dashed red, not "supports"
    g8 = EvidenceGraph.model_validate(c.get("/api/cases/CASE-0008/graph").json())
    assert [n.tier.value for n in g8.nodes if n.kind == "evidence"] == ["supporting"]  # an email alone: dashed border


# ------------------------------------------------------------------ review: policy decides, the API only records
def test_analyst_approves_the_hero_case(trio):
    c, deps = trio
    r = c.post("/api/cases/CASE-0007/review", json={"decision": "approve", "comment": "ok"}, headers=ANALYST)
    res = ReviewResult.model_validate(r.json())
    assert r.status_code == 200 and res.state.value == "APPLIED"
    assert {(a.invoice_id, a.status) for a in res.applied} == {("INV-1042", "applied"), ("INV-1043", "applied")}
    with deps.core.db.tx() as s:
        assert s.get(Invoice, "INV-1042").status == "applied"
    kinds = [e["event_type"] for e in deps.audit.events if e["case_id"] == "CASE-0007"][-3:]
    assert kinds == ["STATE_CHANGED", "REVIEW_DECIDED", "APPLIED"]
    assert deps.audit.events[res.audit_seq - 1]["actor"] == "reviewer:analyst-1"
    assert c.get("/api/audit/verify").json()["ok"] and c.get("/api/cases/CASE-0007").json()["state"] == "APPLIED"
    assert c.post("/api/cases/CASE-0007/review", json={"decision": "approve"}, headers=ANALYST).status_code == 409


def test_probable_and_conflicting_cases_cannot_be_approved(trio):
    c, deps = trio
    before = len(deps.audit.events)
    r = c.post("/api/cases/CASE-0008/review", json={"decision": "approve"}, headers=CONTROLLER)
    assert r.status_code == 409 and r.json()["error"] == "policy" and "Probable" in r.json()["detail"]
    r = c.post("/api/cases/CASE-0009/review", json={"decision": "approve"}, headers=CONTROLLER)
    assert r.status_code == 409 and "nobody approves" in r.json()["detail"]
    assert len(deps.audit.events) == before and c.get("/api/cases/CASE-0008").json()["state"] == "AWAITING_EVIDENCE"


def test_review_input_rules(trio):
    c, _ = trio

    def post(body, headers=ANALYST):
        return c.post("/api/cases/CASE-0007/review", json=body, headers=headers)
    assert post({"decision": "approve"}, {}).json()["error"] == "reviewer_required"
    assert post({"decision": "approve"}, {"X-Reviewer-Id": "nobody"}).json()["error"] == "unknown_reviewer"
    assert post({"decision": "reject"}).json()["error"] == "comment_required"
    assert post({"decision": "request_evidence", "comment": "  "}).status_code == 422
    assert post({"decision": "approve", "sneaky": 1}).status_code == 422  # unknown fields are refused
    assert post({"decision": "shrug"}).status_code == 422
    ok = post({"decision": "request_evidence", "comment": "need the TDS certificate"})
    assert ok.status_code == 200 and ok.json()["state"] == "AWAITING_EVIDENCE"


def test_the_analysts_limit_blocks_a_large_approval(trio):
    c, deps = trio
    with deps.core.db.tx() as s:
        a = s.scalars(select(Adjustment).where(Adjustment.case_id == "CASE-0007")).one()
        a.amount_paise = 10_00_001 * 100  # booking more than the analyst's 10,00,000
    r = c.post("/api/cases/CASE-0007/review", json={"decision": "approve"}, headers=ANALYST)
    assert r.status_code == 409 and "approval limit" in r.json()["detail"]
    assert c.post("/api/cases/CASE-0007/review", json={"decision": "approve"}, headers=CONTROLLER).status_code == 200


# ------------------------------------------------------------------ hardening
def test_security_headers_and_no_docs_page(trio):
    c, _ = trio
    h = c.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in h["content-security-policy"] and h["referrer-policy"] == "no-referrer"
    assert c.get("/docs").status_code == 404 and c.get("/api/openapi.json").status_code == 200


def test_optional_bearer_token_guards_write_routes(trio, monkeypatch):
    c, _ = trio
    monkeypatch.setenv("ARTEMIS_API_TOKEN", "s3cret")
    assert c.post("/api/cases/CASE-0007/review", json={"decision": "approve"}, headers=ANALYST).status_code == 401
    assert c.post("/api/reset").status_code == 401 and c.get("/api/cases").status_code == 200  # reads stay public
    ok = c.post("/api/cases/CASE-0007/review", json={"decision": "approve"},
                headers={**ANALYST, "Authorization": "Bearer s3cret"})
    assert ok.status_code == 200


def test_reset_is_demo_only_and_rate_limited(trio, monkeypatch):
    c, _ = trio
    monkeypatch.setenv("DEMO_MODE", "0")
    assert c.post("/api/reset").status_code == 403
    monkeypatch.setenv("DEMO_MODE", "1")
    first = c.post("/api/reset")
    assert first.status_code == 200 and first.json()["auto_closed"] == 10 and first.json()["cases"] == 40
    assert c.get("/api/cases/CASE-0007").json()["state"] == "NEW"  # back to the seed state
    assert c.get("/api/audit/verify").json()["ok"]  # the ledger restarts with the environment
    codes = [c.post("/api/reset").status_code for _ in range(10)]
    assert codes[-1] == 429 and codes[:-1] == [200] * 9


def test_spa_fallback_serves_the_ui_but_never_swallows_api_errors(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>artemis</html>", encoding="utf-8")
    c = TestClient(create_app(build_deps("real", prepare=False), static_dir=dist))
    assert c.get("/cases/CASE-0007").text == "<html>artemis</html>"  # a client-side route
    assert c.get("/api/nope").json()["error"] == "not_found"
    assert c.get("/..%2f..%2fpyproject.toml").text == "<html>artemis</html>"  # path traversal falls back to the UI
