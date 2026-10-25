# Artemis

Synthetic Indian AR reconciliation: a deterministic core, an investigating agent, and a reviewer product, built as three lanes that meet at fixed contracts (see the build spec).

This branch is **Lane B (agent and investigation)**. Lanes A and C plug in through `artemis/ports.py`; until they land, fixture-backed fakes in `artemis/fakes/` stand in, so Lane B runs and tests alone.

## Run it

```bash
uv sync
uv run pytest            # offline, no API key (or: make test)
uv run --env-file .env python -m eval.run --runs 3   # live benchmark, writes eval/report.{json,md}
PYTHONPATH=. uv run python -m eval.run --runs 3 --scripted   # same pipeline, no key (golden agent, not an LLM score)
PYTHONPATH=. uv run python -m artemis.agent.batch --scripted --save runs/batch.json
PYTHONPATH=. uv run python -m artemis.agent.batch --replay runs/batch.json   # zero LLM calls
```

LLM: any OpenAI-compatible endpoint, Groq by default. Copy `.env.example` to `.env` and set `LLM_API_KEY` and `LLM_MODEL` (pick a current tool-calling model; the name is config, never code). `uv run --env-file .env pytest -m live -s` runs the golden hero-case acceptance test against it (`.env` is not auto-loaded; `--env-file` does it).

## Plugging in the other lanes

| Lane | Implements (in `artemis/ports.py`) | Then |
|---|---|---|
| A | `CoreService`, `PolicyEngine` | wire in `artemis/wiring.py:build_deps`, delete the matching `fakes/` file |
| C | `AuditSink` (`append(case_id, event_type, actor, payload)`) | same |

B's code does not change. The tests in `tests/` run against whichever backend `build_deps` returns.

## For UI work (Lane C)

Everything the UI reads from B is a versioned view-model in `artemis/views.py` (`TraceView`, `BatchStatus`, `MetricsReport`) or `CaseOutcome` in `artemis/models.py`: raw paise, enums and ids only, never formatted strings. JSON Schemas are committed in `contracts/` (`uv run python -m scripts.export_schemas` regenerates; a test fails on drift). Generate TypeScript types from those and restyle freely; nothing in the agent depends on how it is displayed.

## Notes for Lane A (found while building B)

- `PolicyEngine.transition` must allow `INVESTIGATING -> NEEDS_REVIEW` (agent error path) and `NEEDS_REVIEW -> INVESTIGATING` (fresh investigation).
- `request_evidence` only logs the request; the agent loop moves the case to `AWAITING_EVIDENCE` after grading, so a request followed by an Insufficient grade cannot strand a case.
- `CoreService.grade` takes the last `AllocationResult` and the case's `Evidence` rows (with tiers) and returns the grade and contradiction flags.
