import json
from pathlib import Path

from scripts.export_openapi import spec

OUT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


def test_committed_openapi_matches_the_api():
    """The UI's TypeScript types are generated from contracts/openapi.json: it must never lag the code
    (fix: uv run python -m scripts.export_openapi, then regenerate the web types)."""
    assert json.loads(OUT.read_text(encoding="utf-8")) == json.loads(json.dumps(spec(), sort_keys=True))


def test_every_route_is_under_api_and_documented():
    paths = spec()["paths"]
    assert paths and all(p.startswith("/api/") for p in paths)
    expected = {"/api/batch/run", "/api/batch/{batch_id}", "/api/cases", "/api/cases/{case_id}",
                "/api/cases/{case_id}/trace", "/api/cases/{case_id}/graph", "/api/cases/{case_id}/review", "/api/audit",
                "/api/audit/verify", "/api/audit/checkpoint", "/api/metrics", "/api/reset", "/api/reviewers",
                "/api/modes", "/api/health"}
    assert expected <= set(paths)  # every route in the build spec's API table
