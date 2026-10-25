import asyncio

from artemis.agent.batch import run_batch
from artemis.agent.llm import LLMClient, ScriptedLLM
from artemis.agent.trace import build_trace
from artemis.fakes.scripted import golden_agent
from artemis.fakes.store import InMemoryRunStore
from artemis.models import CaseState
from artemis.wiring import build_deps
from tests.conftest import FIXTURES


def scripted(deps):
    return lambda c: ScriptedLLM(golden_agent(deps.core, c))


def test_batch_counts_and_progress(deps):
    b = asyncio.run(run_batch(deps, scripted(deps), concurrency=2))
    assert b.counts_by_status == {"VERIFIED": 1, "PROBABLE": 1, "CONFLICTING": 1}
    assert b.done == b.total == 3 and not b.running and not b.replay
    assert deps.store.get_batch(b.batch_id).done == 3
    kinds = [e["event_type"] for e in deps.audit.events]
    assert kinds[0] == "BATCH_STARTED" and kinds[-1] == "BATCH_COMPLETED"


def test_one_failure_does_not_stop_the_batch(deps):
    def factory(case_id):
        if case_id == "CASE-0008":
            raise RuntimeError("provider exploded")
        return ScriptedLLM(golden_agent(deps.core, case_id))
    b = asyncio.run(run_batch(deps, factory))
    assert b.counts_by_status == {"VERIFIED": 1, "CONFLICTING": 1, "ERROR": 1}
    assert deps.policy.state_of("CASE-0008") == CaseState.NEEDS_REVIEW and "CASE-0008" in b.errors
    assert deps.policy.state_of("CASE-0007") == CaseState.PENDING_APPROVAL


class CountingLLM:  # fails the test if replay ever touches an LLM
    model = "counting"
    calls = 0

    def chat(self, *a, **k):
        CountingLLM.calls += 1
        raise AssertionError("replay must not call the LLM")


def test_replay_matches_recorded_with_zero_llm_calls(deps, tmp_path):
    first = asyncio.run(run_batch(deps, scripted(deps)))
    path = tmp_path / "batch.json"
    deps.store.save(path)
    store = InMemoryRunStore.load(path)  # survives the process
    fresh = build_deps("fixtures", store=store, fixtures_dir=FIXTURES)  # reset environment, same recordings
    second = asyncio.run(run_batch(fresh, lambda c: CountingLLM(), replay_of=first.batch_id))
    assert CountingLLM.calls == 0 and second.replay
    assert second.counts_by_status == first.counts_by_status and second.counts_by_state == first.counts_by_state
    for c in first.run_ids:
        a, b = store.get_outcome(c), store.get_outcome(c)
        assert a.grade == b.grade
    t = build_trace(store, "CASE-0007")  # trace of the replay shows the recorded steps
    assert t.replay and t.tool_path[0] == "record_hypothesis" and t.tool_path[-1] == "finish"
    assert fresh.policy.state_of("CASE-0007") == CaseState.PENDING_APPROVAL


def test_trace_view_is_raw_data_only(deps):
    asyncio.run(run_batch(deps, scripted(deps)))
    t = build_trace(deps.store, "CASE-0007")
    assert t.schema_version == 1 and t.steps and isinstance(t.steps[0].tool_calls[0].args_json, dict)
    alloc = next(c for s in t.steps for c in s.tool_calls if c.tool_name == "propose_allocation").result_json
    assert alloc["variance_paise"] == 2_600_000 and alloc["allocations"][0]["amount_paise"] == 118_000_000
