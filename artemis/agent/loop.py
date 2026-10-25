"""The investigation loop. B never writes money logic or cases.state directly: numbers come back from
tools (Lane A's code underneath) and every state change goes through deps.policy."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from artemis.agent.llm import LLMClient, assistant_message
from artemis.agent.narrative import TEMPLATE_VERSION, build_narrative, template_narrative
from artemis.agent.replay import Replayer, ReplayExhausted
from artemis.money import quarter_of
from artemis.models import (AgentRun, CaseOutcome, CaseState, EvidenceStatus, StopReason, ToolCall)
from artemis.ports import IllegalTransition
from artemis.tools import registry
from artemis.tools.base import ToolContext

PROMPT_VERSION = "investigate_v2"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
_NEXT = {EvidenceStatus.VERIFIED: CaseState.PENDING_APPROVAL, EvidenceStatus.PROBABLE: CaseState.AWAITING_EVIDENCE,
         EvidenceStatus.INSUFFICIENT: CaseState.NEEDS_REVIEW, EvidenceStatus.CONFLICTING: CaseState.NEEDS_REVIEW}
_OBS_CHARS = 8000
REJECTED = "(rejected)"  # pseudo tool name for calls the provider refused before we saw them


@dataclass(frozen=True)
class Limits:  # enforced in code, not in the prompt
    max_steps: int = 12
    max_seconds: float = 90.0
    max_tokens: int = 40_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run_case(case_id: str, deps, llm: LLMClient, *, limits: Limits = Limits(), replayer: Replayer | None = None,
             clock=time.monotonic) -> CaseOutcome:
    store, audit, policy = deps.store, deps.audit, deps.policy
    if replayer:
        llm = replayer
    run = AgentRun(id=store.next_id("RUN"), case_id=case_id, model=llm.model, prompt_version=PROMPT_VERSION,
                   started_at=_now(), replay_of=replayer.run.id if replayer else None)
    store.save_run(run)
    ctx = ToolContext(deps=deps, llm=llm, case_id=case_id, run_id=run.id)
    execute = replayer.execute if replayer else registry.execute
    path: list[str] = []
    try:
        policy.transition(case_id, CaseState.INVESTIGATING, "agent")
        audit.append(case_id, "INVESTIGATION_STARTED", "agent",
                     {"run_id": run.id, "model": run.model, "prompt_version": PROMPT_VERSION,
                      "replay_of": run.replay_of})
        opening = deps.core.opening_context(case_id)
        if "value_date" in opening.get("receipt", {}):  # dates are computed by code, never by the model
            opening["financial_quarter"] = quarter_of(date.fromisoformat(opening["receipt"]["value_date"]))
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Opening context (built by code):\n" + json.dumps(opening)}]
        stop, last_sig, nudges, t0 = None, None, 0, clock()
        while stop is None:
            if run.steps >= limits.max_steps:
                stop = StopReason.MAX_STEPS
            elif clock() - t0 - getattr(llm, "throttled_seconds", 0.0) > limits.max_seconds:
                stop = StopReason.TIMEOUT
            elif run.tokens_in + run.tokens_out + ctx.tokens_in + ctx.tokens_out >= limits.max_tokens:
                stop = StopReason.TOKEN_CAP
            if stop:
                break
            try:
                resp = llm.chat(messages, registry.schemas())
            except ReplayExhausted:
                stop = replayer.run.stop_reason or StopReason.FINISHED
                break
            run.steps += 1
            run.tokens_in += resp.tokens_in
            run.tokens_out += resp.tokens_out
            if not resp.tool_calls:
                nudges += 1
                if nudges >= 3:
                    stop = StopReason.ERROR
                    break
                if resp.error:  # provider rejected the call (e.g. invalid enum): tell the model, let it retry
                    if not replayer:  # keep it in the trace: rejected attempts are part of what the agent did
                        store.add_tool_call(ToolCall(id=store.next_id("CALL"), run_id=run.id, step=run.steps,
                                                     tool_name=REJECTED, args_json={}, result_json={"error": resp.error}))
                    messages.append({"role": "user", "content": "Your last tool call was rejected: " + resp.error
                                     + " Fix the arguments and call the tool again."})
                else:
                    messages += [assistant_message(resp), {"role": "user", "content":
                                 "Call a tool. Use record_hypothesis, then an evidence tool; call finish when done."}]
                continue
            nudges = 0
            messages.append(assistant_message(resp))
            for tc in resp.tool_calls:
                sig = (tc.name, json.dumps(tc.arguments, sort_keys=True))
                if sig == last_sig:
                    stop = StopReason.LOOP
                    break
                last_sig = sig
                ctx.step, ctx.call_id = run.steps, (tc.id if replayer else store.next_id("CALL"))
                t = clock()
                if tc.name == "finish" and ctx.state.allocation is None:
                    result = {"error": "refused", "detail": "call propose_allocation at least once before finish"}
                else:
                    result = execute(tc.name, tc.arguments, ctx)
                path.append(tc.name)
                if not replayer:
                    store.add_tool_call(ToolCall(id=ctx.call_id, run_id=run.id, step=run.steps, tool_name=tc.name,
                                                 args_json=tc.arguments, result_json=result,
                                                 latency_ms=int((clock() - t) * 1000)))
                audit.append(case_id, "TOOL_CALLED", "agent",
                             {"tool_call_id": ctx.call_id, "tool": tc.name, "result_sha256": _sha(result)})
                obs = json.dumps(result)
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": obs if len(obs) <= _OBS_CHARS else obs[:_OBS_CHARS] + "...[truncated]"})
                if ctx.state.finished:
                    stop = StopReason.FINISHED
                    break
        run.tokens_in += ctx.tokens_in
        run.tokens_out += ctx.tokens_out
        run.stop_reason, run.ended_at = stop, _now()
        store.save_run(run)

        alloc = ctx.state.allocation  # graded on the last propose_allocation, or INSUFFICIENT if none
        grade = deps.core.grade(case_id, alloc, store.evidence(case_id))
        audit.append(case_id, "GRADED", "agent", {"run_id": run.id, "status": grade.status.value,
                     "unexplained_paise": grade.unexplained_paise, "flags": [f.code for f in grade.flags],
                     "duplicate": grade.duplicate})
        policy.transition(case_id, CaseState.GRADED, "agent")
        if grade.status == EvidenceStatus.PROBABLE and not ctx.state.evidence_requested:
            audit.append(case_id, "EVIDENCE_REQUESTED", "system",
                         {"request_id": store.next_id("ER"), "what": "primary evidence for supporting-only adjustment"})
        policy.transition(case_id, _NEXT[grade.status], "agent")

        calls = store.tool_calls(replayer.run.id if replayer else run.id)
        rules = [c.result_json["rule_ref"] for c in calls if c.tool_name == "compute_withholding"
                 and "rule_ref" in c.result_json]
        cited = sorted({e for a in (alloc.adjustments if alloc else []) for e in a.evidence_ids})
        tpl = template_narrative(alloc, grade, rules, cited)
        use_llm = llm if (deps.settings.llm_narrative and not replayer) else None
        text, source = build_narrative(tpl, use_llm)
        audit.append(case_id, "NARRATIVE_GENERATED", "agent", {"source": source, "template_version": TEMPLATE_VERSION,
                     "narrative_sha256": _sha(text)})
        out = CaseOutcome(case_id=case_id, run_id=run.id, grade=grade, allocation=alloc, narrative=text,
                          narrative_source=source, final_state=_NEXT[grade.status], stop_reason=stop, tool_path=path)
    except Exception as e:  # one failure never takes the batch down: case -> NEEDS_REVIEW, stop_reason=error
        run.stop_reason, run.ended_at = StopReason.ERROR, _now()
        store.save_run(run)
        audit.append(case_id, "INVESTIGATION_FAILED", "system", {"run_id": run.id, "error": type(e).__name__})
        try:
            policy.transition(case_id, CaseState.NEEDS_REVIEW, "system")
            final = CaseState.NEEDS_REVIEW
        except IllegalTransition:
            final = policy.state_of(case_id)
        out = CaseOutcome(case_id=case_id, run_id=run.id, grade=None, final_state=final,
                          stop_reason=StopReason.ERROR, tool_path=path, narrative=f"Run failed: {type(e).__name__}: {str(e)[:200]}")
    store.save_outcome(out)
    return out
