"""Resets the environment, runs a full batch N times, compares to the answer key, writes
eval/report.json + eval/report.md. Exits non-zero if the benchmark gate fails."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from artemis.agent.batch import run_batch
from artemis.agent.llm import OpenAICompatClient, ScriptedLLM
from artemis.fakes.scripted import golden_agent
from artemis.models import CaseState
from artemis.views import MetricsReport
from artemis.wiring import build_deps
from eval.metrics import STATUSES, aggregate, compute, gate_ok


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def to_markdown(r: MetricsReport, label: str) -> str:
    cols = STATUSES + ["ERROR"]
    rows = [("Verified precision", pct(r.verified_precision), "100% (0 false clears)"),
            ("Evidence coverage", pct(r.evidence_coverage), "100%"),
            ("Abstention accuracy", pct(r.abstention_accuracy), "100%"),
            ("Autonomous completion", pct(r.autonomous_completion), "measured"),
            ("Status accuracy", pct(r.status_accuracy), "measured"),
            ("Allocation accuracy", pct(r.allocation_accuracy), "measured"),
            ("Tool-path diversity", str(r.tool_path_diversity), "measured"),
            ("Mean steps / tokens / seconds",
             f"{r.mean_steps:.1f} / {r.mean_tokens:.0f} / {r.mean_seconds:.1f}", "measured")]
    md = [f"# Artemis evaluation report ({label})", "",
          f"Synthetic-benchmark results: {r.cases} cases, {r.runs} run(s). Not real-world accuracy.", "",
          "| Metric | Result | Target |", "|---|---|---|", *[f"| {a} | {b} | {c} |" for a, b, c in rows], "",
          f"False clears: {r.false_clears or 'none'}. Red-team cases APPLIED: {r.red_team_applied or 'none'}.", "",
          "## Status confusion (rows = answer key, columns = graded)", "",
          "| key / graded | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for t in STATUSES:
        if t in r.confusion:
            md.append(f"| {t} | " + " | ".join(str(r.confusion[t].get(g, 0)) for g in cols) + " |")
    if r.runs > 1:
        md += ["", "## Spread across runs", ""] + [f"- {k}: {v}" for k, v in r.spread.items()]
    return "\n".join(md) + "\n"


def one_run(scripted: bool, fixtures: str, truth: dict, backend: str) -> MetricsReport:
    deps = build_deps(backend, fixtures_dir=fixtures)  # fresh environment + store every run
    s = deps.settings
    factory = ((lambda c: ScriptedLLM(golden_agent(deps.core, c))) if scripted else
               (lambda c: OpenAICompatClient(s.llm_base_url, s.llm_api_key, s.llm_model)))
    asyncio.run(run_batch(deps, factory))
    auto = frozenset(c for c in truth if deps.policy.state_of(c) == CaseState.AUTO_CLOSED)
    return compute(deps.store.outcomes(), {r.id: r for r in deps.store.runs()}, truth,
                   price_in=s.price_in_paise_per_mtok, price_out=s.price_out_paise_per_mtok, auto_closed=auto)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--scripted", action="store_true", help="offline golden agent (pipeline check, not an LLM score)")
    ap.add_argument("--backend", choices=("fixtures", "real"), default="fixtures",
                    help="fixtures = Lane B's 3 hero cases; real = Lane A's full 40-case environment")
    ap.add_argument("--fixtures", default="fixtures")
    ap.add_argument("--out", default="eval")
    a = ap.parse_args(argv)
    key = Path("data") / "cases_truth.json" if a.backend == "real" else Path(a.fixtures) / "cases_truth.json"
    truth = json.loads(key.read_text(encoding="utf-8"))
    report = aggregate([one_run(a.scripted, a.fixtures, truth, a.backend) for _ in range(a.runs)])
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    md = to_markdown(report, "scripted agent" if a.scripted else "live LLM")
    (out / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out / "report.md").write_text(md, encoding="utf-8")
    print(md)
    return 0 if gate_ok(report) else 1


if __name__ == "__main__":
    sys.exit(main())
