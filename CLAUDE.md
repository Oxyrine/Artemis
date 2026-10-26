# Artemis

Synthetic Indian accounts-receivable reconciliation: a deterministic core (Lane A), an LLM investigation agent (Lane B) and a reviewer product (Lane C), meeting at fixed contracts. Lanes A and B exist; Lane C (FastAPI, hash-chained audit ledger, React UI) does not yet. The build spec is `Artemis — Build Spec.pdf` (not in the repo).

## Commands

```bash
uv run pytest                                   # ~140 tests, offline, no API key; live tests are deselected
uv run --env-file .env pytest -m live -s        # golden hero case + twins on the real model (~8 min on a small Groq tier)
uv run python -m data.generator.generate        # rebuild data/env + data/cases_truth.json (must stay byte-identical)
uv run python -m scripts.export_schemas         # regenerate contracts/*.schema.json (a test fails on drift)
uv run python -m eval.run --backend real --scripted --runs 3   # full 40-case pipeline with the offline oracle agent
ARTEMIS_BACKEND=real uv run --env-file .env python -m scripts.debug_case CASE-0033     # trace one live case
```

`make` is not installed on this machine; the Makefile is a convenience only. Python is 3.14 locally (the spec says 3.11; a Windows Application Control policy blocks uv's managed 3.11).

## Architecture

- `artemis/ports.py` is the seam: `CoreService` and `PolicyEngine` (Lane A), `AuditSink` (Lane C), `RunStore` (Lane B). Everything else codes against these.
- `artemis/wiring.py:build_deps("fixtures"|"real")` is the only place a backend is chosen. `fixtures` = Lane B's fakes in `artemis/fakes/` (3 hero cases); `real` = `SqlCore` + `SqlPolicy` on SQLite (`DATABASE_URL` to override).
- Lane B: `artemis/agent/` (loop, llm client, batch, replay, narrative, trace), `artemis/tools/` (12 tools, one file each, schemas generated from the Pydantic input models), `eval/`, prompts in `artemis/agent/prompts/` (versioned; `PROMPT_VERSION` in `loop.py`).
- Lane A: `artemis/db.py`, `ingest/`, `matching/`, `rules/`, `grading/`, `core.py`; the generator is `data/generator/generate.py`.
- UI-facing view-models are in `artemis/views.py` (raw paise/enums/ids only, versioned); JSON Schemas are committed in `contracts/`.
- `artemis/fakes/scripted.py` is the offline "oracle" agent: it uses only the tool port, so it drives both backends and lets the whole pipeline run free.

## Rules that must hold

1. The LLM never computes money, tax or eligibility; it calls a tool. 2. Nothing becomes APPLIED without a named reviewer. 3. Every state change writes an audit event: `grading/policy.py` is the only writer of `cases.state`. 4. Money is integer paise everywhere (`money.to_paise` takes strings, never floats). 5. Changing a shared schema (`models.py`, `ports.py`, `views.py`) needs the other lanes told first.

## Gotchas

- Do not `source .env` in bash: the key line has a space after `=` and bash prints the key as a "command not found" error. Use `uv run --env-file .env`.
- `data/env/**` is `-text` in `.gitattributes`: the `.eml` files are CRLF on purpose and Windows autocrlf would change their bytes.
- Large bash heredocs (>~5 KB) fail to parse in this environment; write big files with the editor tool.
- The matcher learns aliases from resolved payers; keep scenario-3 (medium confidence) customers out of the generator's random pools.
- Live runs on a small Groq tier (8k tokens/min) are slow by design: the client sleeps out 429s and the wall-time bound excludes that wait.

## Git

Commit and push every change. Author and committer: `Aakash A <230161983+Oxyrine@users.noreply.github.com>` (GitHub blocks pushes that expose the real email). No `Co-Authored-By: Claude` trailer. Branches: `lane-a`, `lane-b`, `main`.
