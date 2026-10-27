from __future__ import annotations

import itertools
from collections import defaultdict

from artemis.models import AgentRun, Evidence, Hypothesis, ToolCall
from artemis.views import BatchStatus


class InMemoryRunStore:
    def __init__(self) -> None:
        self._n: dict[str, itertools.count] = defaultdict(lambda: itertools.count(1))
        self._runs: dict[str, AgentRun] = {}
        self._calls: dict[str, list[ToolCall]] = defaultdict(list)
        self._hyps: dict[str, list[Hypothesis]] = defaultdict(list)
        self._ev: dict[str, list[Evidence]] = defaultdict(list)
        self._batches: dict[str, BatchStatus] = {}
        self._outcomes: dict = {}

    def next_id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._n[prefix]):04d}"

    def save_run(self, run: AgentRun) -> None:
        self._runs[run.id] = run

    def get_run(self, run_id: str) -> AgentRun:
        return self._runs[run_id]

    def runs(self, case_id: str | None = None) -> list[AgentRun]:
        return [r for r in self._runs.values() if case_id in (None, r.case_id)]

    def add_tool_call(self, call: ToolCall) -> None:
        self._calls[call.run_id].append(call)

    def tool_calls(self, run_id: str) -> list[ToolCall]:
        return list(self._calls[run_id])

    def add_hypothesis(self, h: Hypothesis) -> None:
        self._hyps[h.run_id].append(h)

    def hypotheses(self, run_id: str) -> list[Hypothesis]:
        return list(self._hyps[run_id])

    def add_evidence(self, ev: Evidence) -> None:
        self._ev[ev.case_id].append(ev)

    def evidence(self, case_id: str) -> list[Evidence]:
        return list(self._ev[case_id])

    def save_batch(self, batch: BatchStatus) -> None:
        self._batches[batch.batch_id] = batch.model_copy(deep=True)

    def get_batch(self, batch_id: str) -> BatchStatus:
        return self._batches[batch_id]

    # outcomes (per-case result of an investigation)
    def save_outcome(self, outcome) -> None:
        self._outcomes[outcome.case_id] = outcome

    def get_outcome(self, case_id: str):
        return self._outcomes[case_id]

    def outcomes(self) -> list:
        return list(self._outcomes.values())

    # JSON persistence so a recorded batch survives the process (replay is the offline demo fallback)
    def to_dict(self) -> dict:
        dump = lambda xs: [x.model_dump(mode="json") for x in xs]  # noqa: E731
        return {"runs": dump(self._runs.values()), "calls": dump(c for v in self._calls.values() for c in v),
                "hyps": dump(h for v in self._hyps.values() for h in v), "ev": dump(e for v in self._ev.values() for e in v),
                "batches": dump(self._batches.values()), "outcomes": dump(self._outcomes.values())}

    def save(self, path) -> None:
        import json
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path) -> "InMemoryRunStore":
        import json
        from pathlib import Path
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, d: dict) -> "InMemoryRunStore":
        import re
        from artemis.models import AgentRun, CaseOutcome, Evidence, Hypothesis, ToolCall
        s = cls()
        for r in d["runs"]:
            s.save_run(AgentRun(**r))
        for c in d["calls"]:
            s.add_tool_call(ToolCall(**c))
        for h in d["hyps"]:
            s.add_hypothesis(Hypothesis(**h))
        for e in d["ev"]:
            s.add_evidence(Evidence(**e))
        for b in d["batches"]:
            s.save_batch(BatchStatus(**b))
        for o in d["outcomes"]:
            s.save_outcome(CaseOutcome(**o))
        top: dict[str, int] = {}
        for k in ("runs", "calls", "hyps", "ev"):
            for x in d[k]:
                prefix, n = re.match(r"(.+)-(\d+)$", x["id"]).groups()
                top[prefix] = max(top.get(prefix, 0), int(n))
        for b in d["batches"]:
            top["BATCH"] = max(top.get("BATCH", 0), int(b["batch_id"].rsplit("-", 1)[1]))
        for prefix, n in top.items():  # resume id counters past anything recorded
            s._n[prefix] = itertools.count(n + 1)
        return s
