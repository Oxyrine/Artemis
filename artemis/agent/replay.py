"""Replay a recorded run with zero LLM calls: the recorded tool calls are served as the 'model', and the
recorded results stand in for tool execution."""
from __future__ import annotations

from artemis.agent.llm import LLMResponse, ToolCallReq
from artemis.models import AgentRun, AllocationResult, ToolCall


class ReplayExhausted(Exception):
    pass


class Replayer:
    model = "replay"

    def __init__(self, run: AgentRun, calls: list[ToolCall]):
        self.run = run
        self._steps: list[list[ToolCall]] = []
        for c in sorted(calls, key=lambda c: c.step):
            if not self._steps or self._steps[-1][0].step != c.step:
                self._steps.append([])
            self._steps[-1].append(c)
        self._i = 0
        self._queue: list[ToolCall] = []

    # --- LLMClient
    def chat(self, messages, tools=None, *, json_mode=False) -> LLMResponse:
        if self._i >= len(self._steps):
            raise ReplayExhausted()
        step = self._steps[self._i]
        self._i += 1
        self._queue += step
        return LLMResponse(tool_calls=[ToolCallReq(c.id, c.tool_name, c.args_json) for c in step])

    # --- executor: recorded results instead of running tools (state effects mirrored from the result)
    def execute(self, name: str, args: dict, ctx) -> dict:
        c = self._queue.pop(0)
        res = c.result_json
        if "error" not in res:
            if name == "propose_allocation":
                ctx.state.allocation = AllocationResult.model_validate(res)
            elif name == "request_evidence":
                ctx.state.evidence_requested = True
            elif name == "finish":
                ctx.state.finished, ctx.state.summary = True, args.get("summary", "")
        return res
