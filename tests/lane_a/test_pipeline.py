"""The whole of Lane A end to end, no API key: ingest -> match -> investigate (oracle agent on the tool port) ->
grade -> policy, on all 40 cases, compared with the answer key."""
import asyncio

from sqlalchemy import select

from artemis.agent.batch import run_batch
from artemis.agent.llm import ScriptedLLM
from artemis.db import Allocation, Invoice
from artemis.fakes.scripted import golden_agent
from artemis.models import CaseState
from eval.metrics import compute, gate_ok
from tests.lane_a.conftest import TRUTH
from tests.conftest import make


def run_all(deps):
    return asyncio.run(run_batch(deps, lambda c: ScriptedLLM(golden_agent(deps.core, c)), concurrency=2))


def test_forty_cases_reproduce_the_answer_key_exactly(real):
    batch = run_all(real)
    assert batch.total == 30 and not batch.errors  # 10 closed by the matcher, 30 exceptions investigated
    outcomes = {o.case_id: o for o in real.store.outcomes()}
    for cid, t in TRUTH.items():
        if t["status"] == "AUTO_CLOSED":
            assert real.policy.state_of(cid) == CaseState.AUTO_CLOSED and cid not in outcomes
        else:
            o = outcomes[cid]
            assert (o.grade.status.value, o.final_state.value) == (t["status"], t["state"]), cid
            assert real.policy.state_of(cid) == o.final_state  # the DB agrees with the outcome
    split = {}
    for cid in TRUTH:
        key = "AUTO_CLOSED" if cid not in outcomes else outcomes[cid].grade.status.value
        split[key] = split.get(key, 0) + 1
    assert split == {"AUTO_CLOSED": 10, "VERIFIED": 16, "PROBABLE": 6, "CONFLICTING": 4, "INSUFFICIENT": 4}


def test_zero_false_clears_and_no_red_team_case_is_ever_applied(real):
    run_all(real)
    auto = frozenset(c for c in TRUTH if real.policy.state_of(c) == CaseState.AUTO_CLOSED)
    m = compute(real.store.outcomes(), {r.id: r for r in real.store.runs()}, TRUTH, auto_closed=auto)
    assert gate_ok(m) and m.verified_precision == 1.0 and m.abstention_accuracy == 1.0 and m.status_accuracy == 1.0
    assert m.cases == 40 and m.false_clears == [] and m.red_team_applied == []
    assert all(real.policy.state_of(c) != CaseState.APPLIED for c in TRUTH)  # nothing is applied without a reviewer
    assert m.evidence_coverage == 1.0 and m.tool_path_diversity >= 5  # the path changes with the evidence


def test_every_verified_case_has_primary_evidence_on_every_adjustment(real):
    run_all(real)
    for o in real.store.outcomes():
        if o.grade.status.value == "VERIFIED":
            ev = {e.id: e for e in real.store.evidence(o.case_id)}
            for a in o.allocation.adjustments:
                assert any(ev[i].tier.value == "primary" for i in a.evidence_ids if i in ev), (o.case_id, a.kind)


def test_the_matcher_applies_only_what_it_closes(real):
    with real.core.db.tx() as s:
        applied = {i.id for i in s.scalars(select(Invoice).where(Invoice.status == "applied"))}
        closed_inv = {a.invoice_id for a in s.scalars(select(Allocation))}
    assert closed_inv <= applied and len(closed_inv) == 10  # 10 auto-closed invoices; the seeded duplicate is separate


def test_the_batch_is_deterministic_run_to_run():
    sig = []
    for _ in range(2):
        d = make("real")
        run_all(d)
        sig.append(sorted((o.case_id, o.grade.status.value, tuple(o.tool_path)) for o in d.store.outcomes()))
    assert sig[0] == sig[1]


def test_a_recorded_batch_replays_identically_with_zero_llm_calls(real):
    first = run_all(real)
    fresh = make("real", real.store)  # environment reset to seed state, same recordings
    calls = []

    class NoLLM:
        model = "none"

        def chat(self, *a, **k):
            calls.append(1)
            raise AssertionError("replay must not call the LLM")
    second = asyncio.run(run_batch(fresh, lambda c: NoLLM(), replay_of=first.batch_id))
    assert not calls and second.replay and second.counts_by_status == first.counts_by_status
    assert second.counts_by_state == first.counts_by_state
