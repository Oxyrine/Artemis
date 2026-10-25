from __future__ import annotations

from artemis.views import TraceStep, TraceView


def build_trace(store, case_id: str) -> TraceView:
    """GET /cases/{id}/trace. A replayed run shows the steps of the run it replays, flagged replay=True."""
    out = store.get_outcome(case_id)
    run = store.get_run(out.run_id)
    src = run.replay_of or run.id
    steps: dict[int, TraceStep] = {}
    for h in store.hypotheses(src):
        steps.setdefault(h.step, TraceStep(step=h.step)).hypotheses.append(h)
    calls = store.tool_calls(src)
    for c in calls:
        steps.setdefault(c.step, TraceStep(step=c.step)).tool_calls.append(c)
    return TraceView(case_id=case_id, run=run, replay=bool(run.replay_of), tool_path=[c.tool_name for c in calls if c.tool_name != "(rejected)"],
                     steps=[steps[k] for k in sorted(steps)])
