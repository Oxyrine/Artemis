# Artemis

Synthetic Indian accounts-receivable reconciliation: a deterministic core (Lane A), an LLM investigation agent (Lane B) and a reviewer product (Lane C), meeting at fixed contracts. All three lanes exist; Lane C is the FastAPI service (`artemis/api/`), the hash-chained audit ledger (`artemis/audit/`) and the React UI (`web/`). The build spec is `Artemis — Build Spec.pdf` (not in the repo).

## Commands

```bash
uv run pytest                                   # ~170 tests, offline, no API key; live tests are deselected
DATABASE_URL=postgresql+psycopg://user@host/artemis uv run pytest   # same suite on Postgres 16 (SQLite does not enforce FKs, Postgres does)
uv run --env-file .env pytest -m live -s        # golden hero case + twins on the real model (~8 min on a small Groq tier)
uv run python -m data.generator.generate        # rebuild data/env + data/cases_truth.json (must stay byte-identical)
uv run python -m scripts.export_schemas         # regenerate contracts/*.schema.json (a test fails on drift)
uv run python -m scripts.export_openapi         # regenerate contracts/openapi.json (a test fails on drift)
uv run alembic revision --autogenerate -m "..." # after any model change (a test fails when models and migrations disagree)
uv run python -m scripts.serve                  # API on :8000 (+ web/dist if built); cd web && npm test / npm run dev for the UI
uv run python -m scripts.seed                   # migrate + signing key + load data/env into DATABASE_URL (idempotent); `make demo` = compose stack, `make demo-local` = same without Docker
make smoke                                      # Playwright smoke (needs a server in demo mode: BASE_URL)
make workflow                                   # full Playwright walkthrough on a FRESHLY SEEDED server (it asserts the 10/16/6/4/4 split); failures are collected, any console/network error fails a step
uv run python -m eval.run --backend real --scripted --runs 3   # full 40-case pipeline with the offline oracle agent
ARTEMIS_BACKEND=real uv run --env-file .env python -m scripts.debug_case CASE-0033     # trace one live case
```

`make` is not installed on this machine; the Makefile is a convenience only. Python is 3.14 on the author's machine and 3.13 in the cloud sandbox (the spec says 3.11; a Windows Application Control policy blocks uv's managed 3.11).

## Architecture

- `artemis/ports.py` is the seam: `CoreService` and `PolicyEngine` (Lane A), `AuditSink` (Lane C), `RunStore` (Lane B). Everything else codes against these.
- `artemis/wiring.py:build_deps("fixtures"|"real")` is the only place a backend is chosen. `fixtures` = Lane B's fakes in `artemis/fakes/` (3 hero cases); `real` = `SqlCore` + `SqlPolicy` on SQLite (`DATABASE_URL` to override).
- Lane B: `artemis/agent/` (loop, llm client, batch, replay, narrative, trace), `artemis/tools/` (12 tools, one file each, schemas generated from the Pydantic input models), `eval/`, prompts in `artemis/agent/prompts/` (versioned; `PROMPT_VERSION` in `loop.py`).
- Lane A: `artemis/db.py`, `ingest/`, `matching/`, `rules/`, `grading/`, `core.py`; the generator is `data/generator/generate.py`.
- Lane C: `artemis/api/` (FastAPI, routes under `/api`, single worker), `artemis/audit/` (`SqlAudit`: hash chain, append-only triggers, signed checkpoints; `build_deps("real")` wires it), `web/` (React + Vite, types generated from `contracts/openapi.json`; onboarding content and the guided-demo script are in `web/src/lib/guide.ts`, path-comparison logic in `web/src/lib/compare.ts`, and the hero case and twins are pinned to CASE-0007/0008/0009 by the generator's answer key), `migrations/` (Alembic, `0001` is the full schema incl. ledger triggers), `deploy/` (compose: postgres + api + web; `scripts/seed.py` is the api entrypoint's first step; `ARTEMIS_PREPARE=0` stops the API wiping the DB on start).
- UI-facing view-models are in `artemis/views.py` (raw paise/enums/ids only, versioned); JSON Schemas are committed in `contracts/`.
- `artemis/fakes/scripted.py` is the offline "oracle" agent: it uses only the tool port, so it drives both backends and lets the whole pipeline run free.

## Rules that must hold

1. The LLM never computes money, tax or eligibility; it calls a tool. 2. Nothing becomes APPLIED without a named reviewer. 3. Every state change writes an audit event: `grading/policy.py` is the only writer of `cases.state`. 4. Money is integer paise everywhere (`money.to_paise` takes strings, never floats). 5. Changing a shared schema (`models.py`, `ports.py`, `views.py`) needs the other lanes told first.

## Gotchas

- `data/generator/generate.py` must not depend on the platform or zlib build: xlsx entries are stored (not deflated) and `cases_truth.json` is written with explicit CRLF. Keep it that way or the byte-identical test fails on other machines.
- No `relationship()` links the models, so SQLAlchemy does not order inserts across tables. `flush()` parents before children (see `ingest/load_all.py`); SQLite hides a miss, Postgres raises an FK violation.
- Do not `source .env` in bash: the key line has a space after `=` and bash prints the key as a "command not found" error. Use `uv run --env-file .env`.
- `data/env/**` is `-text` in `.gitattributes`: the `.eml` files are CRLF on purpose and Windows autocrlf would change their bytes.
- Large bash heredocs (>~5 KB) fail to parse in this environment; write big files with the editor tool.
- The matcher learns aliases from resolved payers; keep scenario-3 (medium confidence) customers out of the generator's random pools.
- Live runs on a small Groq tier (8k tokens/min) are slow by design: the client sleeps out 429s and the wall-time bound excludes that wait.

## Git

Commit and push every change. Author and committer: `Aakash A <230161983+Oxyrine@users.noreply.github.com>` (GitHub blocks pushes that expose the real email). No `Co-Authored-By: Claude` trailer. Branches: `lane-a`, `lane-b`, `main`.
