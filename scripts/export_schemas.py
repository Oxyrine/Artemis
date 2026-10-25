"""Writes JSON Schema for every UI-facing view-model to contracts/ (Lane C generates TS types from these).
`make schemas && git diff --exit-code contracts/` catches contract drift."""
import json
from pathlib import Path

from artemis.models import CaseOutcome
from artemis.views import BatchStatus, MetricsReport, NarrativeView, TraceView

OUT = Path(__file__).resolve().parent.parent / "contracts"

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for m in (TraceView, BatchStatus, MetricsReport, NarrativeView, CaseOutcome):
        (OUT / f"{m.__name__}.schema.json").write_text(
            json.dumps(m.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", len(list(OUT.glob("*.json"))), "schemas")
