from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, exc, inspect, text

import artemis.audit.models  # noqa: F401  (registers the ledger tables)
from artemis.db import Base

ROOT = Path(__file__).resolve().parents[2]


def config(conn) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["connection"] = conn
    return cfg


@pytest.fixture
def engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'm.db'}")


def test_upgrade_head_matches_the_models(engine):
    with engine.begin() as conn:
        command.upgrade(config(conn), "head")
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models changed without a migration: run `uv run alembic revision --autogenerate`: {diff}"


def test_the_ledger_tables_are_append_only_after_migrating(engine):
    with engine.begin() as conn:
        command.upgrade(config(conn), "head")
        conn.execute(text("INSERT INTO audit_events VALUES (1, NULL, 'T', 'system', '{}', :p, :h, 'now')"),
                     {"p": "0" * 64, "h": "1" * 64})
    for sql in ("UPDATE audit_events SET actor = 'x'", "DELETE FROM audit_events"):
        with pytest.raises(exc.DBAPIError, match="append-only"), engine.begin() as conn:
            conn.execute(text(sql))


def test_downgrade_removes_everything(engine):
    with engine.begin() as conn:
        command.upgrade(config(conn), "head")
        command.downgrade(config(conn), "base")
        assert inspect(conn).get_table_names() == ["alembic_version"]
