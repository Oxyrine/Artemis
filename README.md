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

## Lane A (data and deterministic core)

`artemis/` modules, none of which call an LLM: `db.py` (SQLAlchemy 2; SQLite now, Postgres 16 later), `ingest/` (CSV/XLSX/EML into one transaction, loud validation), `matching/` (name normalization and entity resolution, matcher and case builder), `rules/` (versioned TDS table in `tds_rules.yaml`), `grading/` (variance engine, grader, policy engine), `core.py` (`SqlCore`, the `CoreService` implementation).

```bash
uv run python -m data.generator.generate      # rebuild data/env/ + data/cases_truth.json (byte-identical every time)
uv run pytest                                 # every Lane B test also runs on this core (parametrized "real" backend)
uv run python -m eval.run --backend real --scripted --runs 3     # all 40 cases, no API key
ARTEMIS_BACKEND=real uv run --env-file .env python -m scripts.debug_case CASE-0033   # one live case on the real core
```

`build_deps("real")` reloads `data/env`, runs the matcher (10 exact matches auto-close, 30 cases wait as NEW) and returns the Lane A stack on an in-memory SQLite database; set `DATABASE_URL` for a file or Postgres. The Lane B suite, the oracle agent and the evaluation harness run unchanged on either backend.

### Decisions worth knowing
- **Approval limits** apply to what an approval *books as adjustments* (the 26,000 TDS on the hero case), not to the cash received: the spec has the analyst approve the 15,08,000 hero case under a 10,00,000 limit, which only works that way.
- **Aliases are learned.** Every resolved payer writes a `customer_aliases` row and later receipts match against it. The two medium-confidence customers are therefore kept out of the random pools in the generator.
- **Email-only credit notes** become `credit_notes` rows (`email_only` / `agreed_not_issued`, supporting evidence) when Lane B's `parse_remittance` output is saved, so the variance engine can validate them and the grade tops out at PROBABLE.
- **The grader looks for contradictions the agent did not fetch** (a tax-credit row for the same deductor on the payment date, a narration citing another customer's invoice), and a proposed allocation onto an already-applied invoice is a duplicate, never VERIFIED.
- **Flags 1-7** are all implemented. Flag 6 reads an optional `invoice_amounts` key that `parse_remittance` does not emit yet, and flag 7 checks claimed UTRs only.
- **TDS labels and thresholds are config.** `threshold_paise` is `null` (not applied) until checked against the Income Tax Department's published guidance; the UI should say "configured, not advised".

### Hand-offs to Lane C
`SqlPolicy.decide(case_id, reviewer_id, decision)` validates a reviewer's action (Probable and Conflicting cases cannot be approved, limits, duplicate refunds need a controller) and makes the transition; it returns the refusal reason for the UI. Applying allocations to invoices on approve (same transaction) is the API's job. `SqlCore.reset()` is what `POST /reset` calls. The audit sink is still the in-memory `ListAudit` until the hash-chained ledger lands.

### Not done yet
Alembic migrations, a run on Postgres 16, evidence rows for the matcher's own entity matches (they live in `customer_aliases`), dispute flags (no dispute data exists; the hook is `matcher.DISPUTED`).
