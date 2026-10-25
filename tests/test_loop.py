from artemis.agent.llm import LLMResponse, ScriptedLLM, ToolCallReq, tool_msg
from artemis.agent.loop import Limits, run_case
from artemis.agent.narrative import build_narrative, figures
from artemis.models import CaseState, EvidenceStatus as ES, StopReason as SR
from artemis.tools import registry
from artemis.tools.base import ToolContext

CASE = "CASE-0007"


def ledger(i=0):  # distinct args each call so loop detection doesn't fire
    return tool_msg("search_ledger", customer_id="CUST-014", amount_paise=i + 1)


def test_stuck_agent_is_stopped_as_loop(deps):
    out = run_case(CASE, deps, ScriptedLLM(lambda m: tool_msg("search_ledger", customer_id="CUST-014")))
    assert out.stop_reason == SR.LOOP and out.grade.status == ES.INSUFFICIENT  # no allocation -> INSUFFICIENT
    assert out.final_state == CaseState.NEEDS_REVIEW
    assert deps.store.get_run(out.run_id).steps == 2


def test_max_steps_bound(deps):
    n = iter(range(100))
    out = run_case(CASE, deps, ScriptedLLM(lambda m: ledger(next(n))), limits=Limits(max_steps=3))
    assert out.stop_reason == SR.MAX_STEPS and deps.store.get_run(out.run_id).steps == 3


def test_token_cap_and_timeout(deps):
    n = iter(range(100))
    out = run_case(CASE, deps, ScriptedLLM(lambda m: ledger(next(n))), limits=Limits(max_tokens=250))
    assert out.stop_reason == SR.TOKEN_CAP
    d2 = type(deps)(deps.core, type(deps.policy)(deps.audit), deps.audit, deps.store, deps.settings)
    ticks = iter(range(0, 1000, 100))
    out = run_case(CASE, d2, ScriptedLLM(lambda m: ledger(next(n))), limits=Limits(max_seconds=150),
                   clock=lambda: next(ticks))
    assert out.stop_reason == SR.TIMEOUT


def test_finish_refused_until_allocation(deps):
    script = [tool_msg("finish", case_id=CASE, summary="done?"), tool_msg("finish", case_id=CASE, summary="done?")]
    out = run_case(CASE, deps, ScriptedLLM(script))
    calls = deps.store.tool_calls(out.run_id)
    assert calls[0].result_json["error"] == "refused" and "propose_allocation" in calls[0].result_json["detail"]
    assert out.stop_reason == SR.LOOP  # same call twice in a row


def test_errors_are_data_never_raised(deps):
    ctx = ToolContext(deps=deps, llm=None, case_id=CASE, run_id="RUN-1")
    r = registry.execute("compute_withholding", dict(customer_id="CUST-014", invoice_ids=["INV-9999"],
                                                      transaction_date="2026-09-12"), ctx)
    assert r["error"] == "not_found"  # an invoice id the model made up
    assert registry.execute("nope", {}, ctx)["error"] == "unknown_tool"
    assert registry.execute("search_ledger", {"customer_id": 5}, ctx)["error"] == "invalid_input"
    bad = registry.execute("propose_allocation", dict(utrs=["UTR839201"], allocations=[],
                           adjustments=[dict(kind="tds", amount_paise=1, evidence_ids=["EV-9999"])]), ctx)
    assert bad["error"] == "not_found" and "EV-9999" in bad["detail"]


def test_llm_exception_marks_needs_review(deps):
    def boom(m):
        raise RuntimeError("provider down")
    out = run_case(CASE, deps, ScriptedLLM(boom))
    assert out.grade is None and out.stop_reason == SR.ERROR and out.final_state == CaseState.NEEDS_REVIEW


def test_narrative_validator_rejects_invented_figures():
    tpl = "Receipt UTR839201 of INR 15,08,000 matched to INV-1042, INV-1043. Unexplained INR 0. Grade: VERIFIED."
    ok, src = build_narrative(tpl, ScriptedLLM([LLMResponse(text="UTR839201 paid INR 15,08,000 for INV-1042.")]))
    assert src == "llm" and "15,08,000" in ok
    for lie in ("UTR839201 paid INR 15,09,000 for INV-1042.", "UTR839201 paid INV-9999.",
                "Paid INR 15,08,000 plus INR 500."):
        text, src = build_narrative(tpl, ScriptedLLM([LLMResponse(text=lie)]))
        assert (text, src) == (tpl, "template")
    assert figures("INR 26,000.00") == figures("INR 26000")
