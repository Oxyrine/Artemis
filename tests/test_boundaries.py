import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANE_A_PACKAGES = ("artemis.rules", "artemis.matching", "artemis.grading", "artemis.ingest", "artemis.fakes")


def test_agent_imports_nothing_from_lane_a_except_through_tools():
    """No money logic in agent/: it may reach Lane A's code only via the tool layer / the ports."""
    for f in (ROOT / "artemis" / "agent").glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for m in mods:
                if f.name in ("batch.py",) and m.startswith("artemis.fakes"):
                    continue  # CLI entry point only (imports inside main())
                assert not m.startswith(LANE_A_PACKAGES), f"{f.name} imports {m}"


def test_committed_contracts_match_the_models():
    """Fails when a view-model changes without `make schemas`, so Lane C never meets drift on Day 7."""
    from artemis.models import CaseOutcome
    from artemis.views import BatchStatus, MetricsReport, NarrativeView, TraceView
    for m in (TraceView, BatchStatus, MetricsReport, NarrativeView, CaseOutcome):
        committed = json.loads((ROOT / "contracts" / f"{m.__name__}.schema.json").read_text(encoding="utf-8"))
        assert committed == m.model_json_schema(), f"{m.__name__} changed: run `make schemas`"


def test_no_float_money_in_models():
    from artemis.models import AdjustmentProposal, AllocationLine, AllocationResult
    for m in (AdjustmentProposal, AllocationLine, AllocationResult):
        for name, f in m.model_fields.items():
            if name.endswith("_paise"):
                assert f.annotation is int, f"{m.__name__}.{name} must be int paise"
