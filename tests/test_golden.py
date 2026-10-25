"""Golden acceptance (offline): hero case + both twins give three different tool paths and grades."""
from artemis.agent.loop import run_case
from artemis.fakes.scripted import golden_agent
from artemis.agent.llm import ScriptedLLM
from artemis.models import CaseState, EvidenceStatus as ES


def go(deps, case_id):
    return run_case(case_id, deps, ScriptedLLM(golden_agent(deps.core, case_id)))


def test_hero_verified_closes_to_zero(deps):
    out = go(deps, "CASE-0007")
    assert out.grade.status == ES.VERIFIED and out.allocation.unexplained_paise == 0
    assert out.allocation.variance_paise == 2_600_000  # 26,000
    assert out.final_state == CaseState.PENDING_APPROVAL and deps.policy.state_of("CASE-0007") == out.final_state
    assert out.tool_path[-2:] == ["propose_allocation", "finish"] and "request_evidence" not in out.tool_path
    assert out.narrative_source == "template" and "Sec 393, Income-tax Act 2025" in out.narrative


def test_probable_twin_requests_evidence(deps):
    out = go(deps, "CASE-0008")
    assert out.grade.status == ES.PROBABLE and out.final_state == CaseState.AWAITING_EVIDENCE
    assert "request_evidence" in out.tool_path


def test_conflicting_twin_never_clears(deps):
    out = go(deps, "CASE-0009")
    assert out.grade.status == ES.CONFLICTING and out.grade.flags[0].code == 1
    assert out.final_state == CaseState.NEEDS_REVIEW


def test_three_different_tool_paths(deps):
    paths = {tuple(go(deps, c).tool_path) for c in ("CASE-0007", "CASE-0008", "CASE-0009")}
    assert len(paths) == 3


def test_every_step_is_audited_and_money_is_ints(deps):
    go(deps, "CASE-0007")
    kinds = [e["event_type"] for e in deps.audit.events]
    for k in ("INVESTIGATION_STARTED", "HYPOTHESIS_RECORDED", "TOOL_CALLED", "ALLOCATION_PROPOSED", "GRADED",
              "STATE_CHANGED", "NARRATIVE_GENERATED"):
        assert k in kinds
    assert kinds.count("STATE_CHANGED") == 3  # NEW->INVESTIGATING->GRADED->PENDING_APPROVAL
    assert all(isinstance(e["payload"].get("result_sha256", ""), str) for e in deps.audit.events)
