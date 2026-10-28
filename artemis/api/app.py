"""The Artemis API (FastAPI). Every route is under /api; the built UI, when present, is served from / by the same process.

Routes follow the build spec: batch run/progress, case list/detail/trace/graph, review, audit + verify + checkpoint,
metrics, reset. Reviewer identity is a stub (X-Reviewer-Id chosen from a dropdown); POST /cases/{id}/review never changes
state itself: it asks the policy engine, which refuses anything illegal and returns the reason."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from artemis.agent.batch import start_batch
from artemis.agent.llm import OpenAICompatClient, ScriptedLLM
from artemis.agent.trace import build_trace
from artemis.api import assemble
from artemis.audit.tamper import tamper
from artemis.api.security import ApiError, RateLimiter, SecurityMiddleware, require_token
from artemis.api.views import (AppliedInvoice, AuditEventView, AuditList, BatchRunRequest, BatchStarted, CaseDetail,
                               CaseList, EvidenceGraph, ModeInfo, Modes, ResetResult, ReviewRequest, ReviewResult,
                               ReviewerView, TamperResult, VerifyResult)
from artemis.db import Allocation, Case, Invoice, Review, Reviewer, RunSnapshot
from artemis.fakes.scripted import golden_agent
from artemis.fakes.store import InMemoryRunStore
from artemis.models import CaseState
from artemis.ports import IllegalTransition
from artemis.views import BatchStatus, MetricsReport, TraceView
from artemis.wiring import Deps, build_deps
from eval.metrics import compute

ROOT = Path(__file__).resolve().parents[2]
TRUTH_FILE = ROOT / "data" / "cases_truth.json"
LABELS = {"demo": "Demo agent (rule-based, no LLM)", "replay": "Replay of a recorded run", "live": "Live model"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def persist_run_records(d: Deps) -> None:
    """Keep the run records in the database (see RunSnapshot): the process may be restarted, the database is not."""
    db = getattr(d.core, "db", None)
    if db is None:
        return
    with db.tx() as s:
        row = s.get(RunSnapshot, "latest") or RunSnapshot(id="latest", payload={}, saved_at="")
        row.payload, row.saved_at = d.store.to_dict(), _now()
        s.add(row)


def restore_run_records(d: Deps) -> None:
    """Load the last batch's run records, if the database holds them (a reset or a fresh seed has none)."""
    db = getattr(d.core, "db", None)
    if db is None:
        return
    try:
        with db.tx() as s:
            row = s.get(RunSnapshot, "latest")
            payload = row.payload if row else None
    except Exception:  # an un-migrated database has no table yet: start with an empty store, as before
        return
    if payload:
        d.store = InMemoryRunStore.from_dict(payload)


def recover_interrupted(d: Deps) -> list[str]:
    """At start no batch is running, so a case still INVESTIGATING (or GRADED but not yet routed) was cut off by a restart.
    Send it to NEEDS_REVIEW through the policy engine, audited, so it is not stuck forever; cases still NEW are untouched
    and the next batch picks them up."""
    db = getattr(d.core, "db", None)
    if db is None:
        return []
    try:
        with db.tx() as s:
            stuck = list(s.scalars(select(Case.id).where(Case.state.in_([CaseState.INVESTIGATING.value, CaseState.GRADED.value])).order_by(Case.id)))
    except Exception:  # an un-migrated or empty database: nothing to recover
        return []
    for cid in stuck:
        d.audit.append(cid, "INVESTIGATION_FAILED", "system", {"error": "InterruptedByRestart"})
        d.policy.transition(cid, CaseState.NEEDS_REVIEW, "system")
    return stuck


def create_app(deps: Deps | None = None, *, static_dir: Path | str | None = None, runs_dir: Path | str | None = None,
               exports_dir: Path | str | None = None) -> FastAPI:
    # ARTEMIS_PREPARE=0: the database is already migrated and seeded (scripts/seed.py), so do not wipe it on start
    deps = deps or build_deps("real", prepare=os.environ.get("ARTEMIS_PREPARE", "1") != "0")
    runs = Path(runs_dir or os.environ.get("RUNS_DIR") or ROOT / "runs")
    exports = Path(exports_dir or os.environ.get("EXPORTS_DIR") or ROOT / "exports")
    restore_run_records(deps)
    recover_interrupted(deps)
    app = FastAPI(title="Artemis", docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")
    app.state.deps, app.state.limiter = deps, RateLimiter()
    app.state.current = {"batch_id": None}
    # gzip goes in first so it sits INSIDE the security middleware and still sees each response's size (outside it, every
    # response is a stream of unknown length and even a one-line health check would be compressed)
    app.add_middleware(GZipMiddleware, minimum_size=800)
    app.add_middleware(SecurityMiddleware)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError):
        return JSONResponse({"error": e.error, "detail": e.detail}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, e: RequestValidationError):
        return JSONResponse({"error": "invalid_request", "detail": json.loads(json.dumps(e.errors(), default=str))},
                            status_code=422)

    def D() -> Deps:  # always read through app.state: /reset and replay swap the store
        return app.state.deps

    def running() -> bool:
        bid = app.state.current["batch_id"]
        return bool(bid and D().store.get_batch(bid).running)

    def recording() -> Path | None:
        env = os.environ.get("REPLAY_FILE")
        for p in ([Path(env)] if env else []) + [runs / "latest-live.json", runs / "latest-demo.json"]:
            if p.exists():
                return p
        return None

    r = APIRouter(prefix="/api")

    @r.get("/health")
    def health():
        return {"ok": True}

    # ------------------------------------------------------------------ batch
    @r.get("/modes", response_model=Modes)
    def modes():
        s = D().settings
        live_ok = bool(s.llm_api_key and s.llm_model)
        return Modes(modes=[
            ModeInfo(mode="demo", label=LABELS["demo"], available=True, reason=None),
            ModeInfo(mode="replay", label=LABELS["replay"], available=recording() is not None,
                     reason=None if recording() else "no recorded run yet: run the demo agent once to record one"),
            ModeInfo(mode="live", label=LABELS["live"], available=live_ok,
                     reason=None if live_ok else "set LLM_API_KEY and LLM_MODEL on the server")])

    @r.post("/batch/run", response_model=BatchStarted, status_code=202, dependencies=[Depends(require_token)])
    def run_batch_route(body: BatchRunRequest, request: Request):
        app.state.limiter.check(request, "batch", 20)
        if running():
            raise ApiError(409, "batch_running", "a batch is already running")
        d, mode = D(), body.mode
        replay_of = None
        if mode == "replay":
            rec = recording()
            if rec is None:
                raise ApiError(409, "no_recording", "no recorded run to replay yet: run the demo agent once")
            d.core.reset()
            d.core.auto_close()
            d.store = InMemoryRunStore.load(rec)  # the recorded runs are the 'model'; the environment starts from seed
            replay_of = max((b for b in d.store._batches.values() if not b.replay), key=lambda b: b.batch_id).batch_id
            factory = None
        elif mode == "live":
            if not (d.settings.llm_api_key and d.settings.llm_model):
                raise ApiError(409, "no_llm_key", "live mode needs LLM_API_KEY and LLM_MODEL on the server")
            s = d.settings
            factory = lambda c: OpenAICompatClient(s.llm_base_url, s.llm_api_key, s.llm_model)  # noqa: E731
        else:
            factory = lambda c: ScriptedLLM(golden_agent(d.core, c))  # noqa: E731
        if replay_of is None and not d.core.new_case_ids():
            raise ApiError(409, "nothing_to_do", "no new cases to investigate: reset the environment first")

        def finished(batch: BatchStatus) -> None:  # seal the audit chain, and keep a recording for replay
            d.audit.checkpoint(batch.batch_id, out_dir=exports)
            if mode != "replay":
                runs.mkdir(parents=True, exist_ok=True)
                d.store.save(runs / f"latest-{mode}.json")
                persist_run_records(d)

        # the demo and replay agents make no LLM calls, so there is no rate limit to respect: use the spec's four workers
        bid = start_batch(d, factory, replay_of=replay_of, on_done=finished, mode=mode, concurrency=4 if mode != "live" else None)
        app.state.current["batch_id"] = bid
        return BatchStarted(batch_id=bid, mode=mode)

    @r.get("/batch/{batch_id}", response_model=BatchStatus)
    def batch_status(batch_id: str):
        try:
            return D().store.get_batch(batch_id)
        except KeyError:
            raise ApiError(404, "not_found", f"no batch {batch_id}") from None

    # ------------------------------------------------------------------ cases
    @r.get("/cases", response_model=CaseList)
    def cases(status: str | None = None, state: str | None = None):
        return assemble.case_list(D(), status, state)

    @r.get("/cases/{case_id}", response_model=CaseDetail)
    def case(case_id: str):
        try:
            return assemble.detail(D(), case_id)
        except KeyError:
            raise ApiError(404, "not_found", f"no case {case_id}") from None

    @r.get("/cases/{case_id}/trace", response_model=TraceView)
    def trace(case_id: str):
        try:
            return build_trace(D().store, case_id)
        except KeyError:
            raise ApiError(404, "not_found", f"no agent run for {case_id} (auto-closed or not investigated yet)") from None

    @r.get("/cases/{case_id}/graph", response_model=EvidenceGraph)
    def case_graph(case_id: str):
        try:
            return assemble.graph(D(), case_id)
        except KeyError:
            raise ApiError(404, "not_found", f"no case {case_id}") from None

    @r.post("/cases/{case_id}/review", response_model=ReviewResult, dependencies=[Depends(require_token)])
    def review(case_id: str, body: ReviewRequest, x_reviewer_id: str | None = Header(default=None)):
        d = D()
        if not x_reviewer_id:
            raise ApiError(401, "reviewer_required", "choose a reviewer (X-Reviewer-Id header)")
        if body.decision in ("reject", "request_evidence") and not body.comment.strip():
            raise ApiError(422, "comment_required", f"a comment is required to {body.decision.replace('_', ' ')}")
        with d.core.db.tx() as s:  # the state change, the review row and the audit events commit (or roll back) together
            if s.get(Reviewer, x_reviewer_id) is None:
                raise ApiError(401, "unknown_reviewer", f"no reviewer {x_reviewer_id!r}")
            if s.get(Case, case_id) is None:
                raise ApiError(404, "not_found", f"no case {case_id}")
            try:
                to = d.policy.decide(case_id, x_reviewer_id, body.decision)
            except IllegalTransition as e:
                raise ApiError(409, "policy", e.reason) from None
            actor = f"reviewer:{x_reviewer_id}"
            seq = d.audit.append(case_id, "REVIEW_DECIDED", actor, {"decision": body.decision, "state": to.value,
                                                                    "comment": body.comment})
            s.add(Review(case_id=case_id, reviewer_id=x_reviewer_id, decision=body.decision, comment=body.comment,
                         decided_at=_now()))
            applied: list[AppliedInvoice] = []
            if to == CaseState.APPLIED:  # post the allocations: invoices become applied / partially_applied
                for a in s.scalars(select(Allocation).where(Allocation.case_id == case_id)):
                    inv = s.get(Invoice, a.invoice_id)
                    inv.status = "applied" if a.amount_paise >= inv.gross_amount - 100 else "partially_applied"
                    applied.append(AppliedInvoice(invoice_id=inv.id, status=inv.status))
                d.audit.append(case_id, "APPLIED", actor, {"invoices": [a.model_dump() for a in applied]})
            return ReviewResult(case_id=case_id, decision=body.decision, state=to, applied=applied, audit_seq=seq)

    # ------------------------------------------------------------------ audit
    @r.get("/audit", response_model=AuditList)
    def audit(case_id: str | None = None, limit: int = 500):
        rows = D().audit.rows(case_id, min(max(limit, 1), 2000))
        return AuditList(events=[AuditEventView(**D().audit.as_dict(e)) for e in rows])

    @r.get("/audit/verify", response_model=VerifyResult)
    def verify():
        return VerifyResult(**D().audit.verify())

    @r.get("/audit/checkpoint")
    def checkpoint():
        cp = D().audit.latest_checkpoint()
        if cp is None:
            raise ApiError(404, "not_found", "no checkpoint yet: run a batch first")
        return JSONResponse(cp, headers={"Content-Disposition": f'attachment; filename="checkpoint-{cp["seq"]:06d}.json"'})

    # ------------------------------------------------------------------ metrics, reviewers, reset
    @r.get("/metrics", response_model=MetricsReport)
    def metrics():
        d = D()
        outcomes = d.store.outcomes()
        if not outcomes or not TRUTH_FILE.exists():  # 200 with an empty report, not a 404: a fresh load is not an error
            return MetricsReport(runs=0, cases=0, verified_precision=None, evidence_coverage=None, abstention_accuracy=None,
                                 autonomous_completion=None, status_accuracy=None, allocation_accuracy=None, confusion={},
                                 tool_path_diversity=0, mean_steps=0.0, mean_tokens=0.0, mean_seconds=0.0)
        truth = json.loads(TRUTH_FILE.read_text(encoding="utf-8"))
        auto = frozenset(c for c in truth if d.policy.state_of(c) == CaseState.AUTO_CLOSED)
        s = d.settings
        return compute(outcomes, {x.id: x for x in d.store.runs()}, truth, auto_closed=auto,
                       price_in=s.price_in_paise_per_mtok, price_out=s.price_out_paise_per_mtok)

    @r.get("/reviewers", response_model=list[ReviewerView])
    def reviewers():
        with D().core.db.tx() as s:
            return [ReviewerView(id=x.id, name=x.name, role=x.role, approval_limit_paise=x.approval_limit_paise)
                    for x in s.scalars(select(Reviewer).order_by(Reviewer.id))]

    @r.post("/reset", response_model=ResetResult, dependencies=[Depends(require_token)])
    def reset(request: Request):
        if os.environ.get("DEMO_MODE", "1") != "1":
            raise ApiError(403, "disabled", "reset is a demo-only action and is disabled on this server")
        app.state.limiter.check(request, "reset", 10)
        if running():
            raise ApiError(409, "batch_running", "wait for the running batch to finish")
        d = D()
        d.core.reset()
        closed = d.core.auto_close()
        d.store = InMemoryRunStore()
        app.state.current["batch_id"] = None
        with d.core.db.tx() as s:
            total = s.query(Case).count()
        return ResetResult(cases=total, auto_closed=len(closed))

    @r.post("/demo/tamper", response_model=TamperResult, dependencies=[Depends(require_token)])
    def demo_tamper(request: Request):
        """The spec's tamper demo from the UI: edit one audit event as the database owner. Demo-only, like /reset;
        Reset environment starts a clean chain again."""
        if os.environ.get("DEMO_MODE", "1") != "1":
            raise ApiError(403, "disabled", "the tamper demo is disabled on this server")
        app.state.limiter.check(request, "tamper", 10)
        if running():
            raise ApiError(409, "batch_running", "wait for the running batch to finish")
        try:
            return TamperResult(**tamper(D().core.db, latest=True))  # a recent event, so the audit page can show it
        except LookupError as e:
            raise ApiError(409, "nothing_to_tamper", str(e))

    app.include_router(r)

    # ------------------------------------------------------------------ the built UI (single-service hosting)
    dist = Path(static_dir) if static_dir else ROOT / "web" / "dist"
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise ApiError(404, "not_found", f"no route /{path}")
            f = (dist / path).resolve()
            return FileResponse(f if f.is_file() and dist.resolve() in f.parents else dist / "index.html")
    return app
