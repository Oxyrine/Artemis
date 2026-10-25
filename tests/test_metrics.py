from artemis.models import AgentRun, CaseOutcome, CaseState, EvidenceStatus as ES, Grade, StopReason
from eval.metrics import aggregate, compute, gate_ok


def out(case, status, state=CaseState.NEEDS_REVIEW, path=("a",)):
    return CaseOutcome(case_id=case, run_id=f"R-{case}", grade=Grade(status=ES(status), unexplained_paise=0),
                       final_state=state, stop_reason=StopReason.FINISHED, tool_path=list(path))


TRUTH = {"C1": {"status": "VERIFIED", "allocations": []}, "C2": {"status": "CONFLICTING", "allocations": [],
         "is_red_team": True}, "C3": {"status": "PROBABLE", "allocations": []}}


def test_false_clear_fails_the_gate_and_precision_drops():
    os_ = [out("C1", "VERIFIED", CaseState.PENDING_APPROVAL), out("C2", "VERIFIED", CaseState.PENDING_APPROVAL, ("b",)),
           out("C3", "PROBABLE")]
    r = compute(os_, {}, TRUTH)
    assert r.verified_precision == 0.5 and r.false_clears == ["C2"] and not gate_ok(r)
    assert r.confusion["CONFLICTING"] == {"VERIFIED": 1} and r.tool_path_diversity == 2


def test_applied_red_team_case_fails_the_gate():
    r = compute([out("C2", "CONFLICTING", CaseState.APPLIED)], {}, TRUTH)
    assert r.abstention_accuracy == 0.0 and r.red_team_applied == ["C2"] and not gate_ok(r)


def test_clean_run_and_spread():
    os_ = [out("C1", "VERIFIED", CaseState.PENDING_APPROVAL), out("C2", "CONFLICTING"), out("C3", "PROBABLE")]
    runs = {f"R-{c}": AgentRun(id=f"R-{c}", case_id=c, model="m", prompt_version="v", started_at="2026-01-01T00:00:00.000",
                               ended_at="2026-01-01T00:00:02.000", steps=4, tokens_in=1000, tokens_out=200) for c in TRUTH}
    r = compute(os_, runs, TRUTH, price_in=100, price_out=200)
    assert gate_ok(r) and r.status_accuracy == 1.0 and r.mean_steps == 4 and r.mean_seconds == 2.0
    assert r.estimated_cost_paise == (3000 * 100 + 600 * 200) // 1_000_000 // 3
    assert aggregate([r, r]).spread["mean_steps"] == [4, 4]
