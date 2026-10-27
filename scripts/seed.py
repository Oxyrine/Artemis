"""Bring a database to the demo's starting state: migrate to head, create the audit signing key if it is missing, and
(if the cases table is empty) load data/env and run the matcher so the exact matches are closed. Safe to run twice.
    python -m scripts.seed      [DATABASE_URL, SIGNING_KEY_PATH]
`make demo` runs it inside the api container before the server starts (with ARTEMIS_PREPARE=0)."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from artemis.audit.signing import key_path, load_or_create_key
from artemis.db import Case, Db, Reviewer, normalize_url
from artemis.ingest.load_all import load_all
from artemis.wiring import build_deps

ROOT = Path(__file__).resolve().parent.parent


def migrate(url: str) -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")


def seed(url: str) -> dict:
    migrate(url)
    load_or_create_key()
    db = Db(url)
    with db.tx() as s:
        seeded = s.scalars(select(Case.id).limit(1)).first() is not None
    if not seeded:
        deps = build_deps("real", prepare=False)  # same wiring the API uses; build_deps reads DATABASE_URL itself
        load_all(deps.core.db)  # data/env and the two reviewers, into the tables the migration made (no drop)
        deps.core.auto_close()
    with db.tx() as s:
        return {"cases": len(list(s.scalars(select(Case.id)))), "reviewers": len(list(s.scalars(select(Reviewer.id)))),
                "signing_key": str(key_path())}


if __name__ == "__main__":
    os.chdir(ROOT)
    url = normalize_url(os.environ.get("DATABASE_URL") or "sqlite:///data/artemis.db")
    os.environ["DATABASE_URL"] = url
    print("seeded:", seed(url))
