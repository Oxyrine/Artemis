"""Batch runner: every NEW case independent, bounded concurrency, one failure never stops the batch.
Replay re-plays a recorded batch with zero LLM calls (the UI shows the replay badge via BatchStatus.replay)."""
from __future__ import annotations

import argparse
import asyncio
import threading
from typing import Callable

from artemis.agent.llm import LLMClient
from artemis.agent.loop import Limits, run_case
from artemis.agent.replay import Replayer
from artemis.models import CaseState
from artemis.views import BatchStatus


class _Unavailable:
    """Stands in when a case's LLM client can't even be built (e.g. no API key): run_case then takes its
    normal error path (NEEDS_REVIEW, stop_reason=error) and the rest of the batch carries on."""
    model = "unavailable"

    def __init__(self, err: Exception):
        self._err = err

    def chat(self, *a, **k):
        raise self._err


def _client(factory, case_id):
    try:
        return factory(case_id)
    except Exception as e:
        return _Unavailable(e)


def _select(deps, case_ids, replay_of) -> list[str]:
    if case_ids:
        return case_ids
    if replay_of:
        return sorted(deps.store.get_batch(replay_of).run_ids)
    return [c for c in deps.core.new_case_ids() if deps.policy.state_of(c) == CaseState.NEW]


def start_batch(deps, llm_factory: Callable[[str], LLMClient] | None, *, case_ids: list[str] | None = None,
                concurrency: int | None = None, replay_of: str | None = None, limits: Limits = Limits(),
                on_done: Callable[[BatchStatus], None] | None = None, mode: str = "") -> str:
    """Create the batch, return its id at once and run it on a background thread (POST /batch/run polls GET /batch/{id})."""
    ids = _select(deps, case_ids, replay_of)
    batch = BatchStatus(batch_id=deps.store.next_id("BATCH"), replay=bool(replay_of), mode=mode, total=len(ids))
    deps.store.save_batch(batch)

    def work() -> None:
        try:
            asyncio.run(run_batch(deps, llm_factory, case_ids=ids, concurrency=concurrency, replay_of=replay_of,
                                  limits=limits, batch=batch))
        except Exception as e:  # never leave a batch 'running' forever
            batch.running, batch.errors["batch"] = False, f"{type(e).__name__}: {e}"
            deps.store.save_batch(batch)
        finally:
            if on_done:
                on_done(deps.store.get_batch(batch.batch_id))

    threading.Thread(target=work, daemon=True, name=batch.batch_id).start()
    return batch.batch_id


async def run_batch(deps, llm_factory: Callable[[str], LLMClient] | None, *, case_ids: list[str] | None = None,
                    concurrency: int | None = None, replay_of: str | None = None, limits: Limits = Limits(),
                    batch: BatchStatus | None = None) -> BatchStatus:
    store = deps.store
    recorded = store.get_batch(replay_of).run_ids if replay_of else {}
    ids = _select(deps, case_ids, replay_of)
    if batch is None:
        batch = BatchStatus(batch_id=store.next_id("BATCH"), replay=bool(replay_of), total=len(ids))
        store.save_batch(batch)
    deps.audit.append(None, "BATCH_STARTED", "system", {"batch_id": batch.batch_id, "total": len(ids),
                                                        "replay_of": replay_of})
    sem = asyncio.Semaphore(concurrency or deps.settings.concurrency)

    async def one(case_id: str) -> None:
        async with sem:
            replayer = None
            if replay_of:
                orig = recorded[case_id]
                replayer = Replayer(store.get_run(orig), store.tool_calls(orig))
            out = await asyncio.to_thread(run_case, case_id, deps, None if replayer else _client(llm_factory, case_id),
                                          limits=limits, replayer=replayer)
        key = out.grade.status.value if out.grade else "ERROR"
        batch.counts_by_status[key] = batch.counts_by_status.get(key, 0) + 1
        batch.counts_by_state[out.final_state.value] = batch.counts_by_state.get(out.final_state.value, 0) + 1
        batch.run_ids[case_id] = out.run_id
        if out.grade is None:
            batch.errors[case_id] = out.narrative
        batch.done += 1
        store.save_batch(batch)

    await asyncio.gather(*(one(c) for c in ids))
    batch.running = False
    store.save_batch(batch)
    deps.audit.append(None, "BATCH_COMPLETED", "system", {"batch_id": batch.batch_id, "counts": batch.counts_by_status})
    return batch


def main() -> None:  # python -m artemis.agent.batch --scripted | --live  [--save runs/x.json] | --replay runs/x.json
    from artemis.agent.llm import OpenAICompatClient, ScriptedLLM
    from artemis.fakes.scripted import golden_agent
    from artemis.fakes.store import InMemoryRunStore
    from artemis.wiring import build_deps

    ap = argparse.ArgumentParser()
    ap.add_argument("--scripted", action="store_true", help="offline golden agent, no API key")
    ap.add_argument("--live", action="store_true", help="LLM from LLM_* env vars")
    ap.add_argument("--replay", metavar="FILE", help="re-play a saved batch, zero LLM calls")
    ap.add_argument("--save", metavar="FILE")
    a = ap.parse_args()
    store = InMemoryRunStore.load(a.replay) if a.replay else InMemoryRunStore()
    deps = build_deps(store=store)
    if a.replay:
        batch = asyncio.run(run_batch(deps, None, replay_of=max(store._batches)))
    else:
        s = deps.settings
        factory = ((lambda c: ScriptedLLM(golden_agent(deps.core, c))) if a.scripted else
                   (lambda c: OpenAICompatClient(s.llm_base_url, s.llm_api_key, s.llm_model)))
        if not (a.scripted or a.live):
            ap.error("choose --scripted, --live or --replay")
        batch = asyncio.run(run_batch(deps, factory))
    if a.save:
        store.save(a.save)
    print(batch.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
