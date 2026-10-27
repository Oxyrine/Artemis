"""The only place that decides fakes vs real. Swap a lane by changing its line in build_deps()."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from artemis.ports import AuditSink, CoreService, PolicyEngine, RunStore


@dataclass
class Settings:
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    concurrency: int = 2
    llm_narrative: bool = False  # LLM rephrase of the narrative is opt-in (saves budget)
    price_in_paise_per_mtok: int = 0
    price_out_paise_per_mtok: int = 0

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ
        return cls(e.get("LLM_BASE_URL", cls.llm_base_url), e.get("LLM_API_KEY", ""), e.get("LLM_MODEL", ""),
                   int(e.get("BATCH_CONCURRENCY", "2")), e.get("LLM_NARRATIVE") == "1",
                   int(e.get("LLM_PRICE_IN_PAISE_PER_MTOK", "0")), int(e.get("LLM_PRICE_OUT_PAISE_PER_MTOK", "0")))


@dataclass
class Deps:
    core: CoreService
    policy: PolicyEngine
    audit: AuditSink
    store: RunStore
    settings: Settings = field(default_factory=Settings)


def build_deps(backend: str | None = None, *, store: RunStore | None = None, fixtures_dir: str = "fixtures",
               prepare: bool = True) -> Deps:
    """fixtures = Lane B's fakes. real = Lane A's SQL core (in-memory SQLite unless DATABASE_URL is set); with
    prepare=True it reloads data/env and runs the matcher, so cases exist and the exact matches are closed."""
    backend = backend or os.environ.get("ARTEMIS_BACKEND", "fixtures")
    from artemis.fakes.audit import ListAudit
    from artemis.fakes.store import InMemoryRunStore
    if backend == "real":
        from artemis.audit.ledger import SqlAudit
        from artemis.core import SqlCore
        from artemis.db import Db
        from artemis.grading.policy import SqlPolicy
        db = Db(os.environ.get("DATABASE_URL") or "sqlite://")
        audit = SqlAudit(db)  # Lane C's hash-chained, append-only ledger, in the same database and transactions
        policy = SqlPolicy(db, audit)
        core = SqlCore(db, policy, audit)
        if prepare:
            core.reset()
            core.auto_close()
        return Deps(core, policy, audit, store or InMemoryRunStore(), Settings.from_env())
    if backend != "fixtures":
        raise ValueError(f"unknown backend {backend!r} (fixtures | real)")
    from artemis.fakes.core import FixtureCore
    from artemis.fakes.policy import FakePolicy
    audit = ListAudit()
    return Deps(FixtureCore(fixtures_dir), FakePolicy(audit), audit, store or InMemoryRunStore(), Settings.from_env())
