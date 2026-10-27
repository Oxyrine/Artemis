"""Lane C: the tamper-evident ledger's tables. Both are append-only: a trigger raises on any UPDATE or DELETE (SQLite and
Postgres variants below). payload_json holds exactly the canonical text that was hashed."""
from __future__ import annotations

from sqlalchemy import Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from artemis.db import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    case_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)  # system | agent | reviewer:<id>
    payload_json: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String)


class AuditCheckpoint(Base):
    __tablename__ = "audit_checkpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seq: Mapped[int] = mapped_column(Integer)
    hash: Mapped[str] = mapped_column(String(64))
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
    signature: Mapped[str] = mapped_column(String)  # base64 Ed25519 over the canonical checkpoint body
    public_key: Mapped[str] = mapped_column(String)  # base64 raw public key, for offline verification


def trigger_statements(table: str, dialect: str) -> list[str]:
    """DDL making `table` append-only: any UPDATE or DELETE raises (a second guard behind the app role's grants)."""
    if dialect == "sqlite":
        return [f"CREATE TRIGGER IF NOT EXISTS {table}_no_{verb.lower()} BEFORE {verb} ON {table} BEGIN "
                f"SELECT RAISE(ABORT, '{table} is append-only'); END" for verb in ("UPDATE", "DELETE")]
    if dialect == "postgresql":
        return [f"CREATE OR REPLACE FUNCTION {table}_append_only() RETURNS trigger AS $$ BEGIN "
                f"RAISE EXCEPTION '{table} is append-only'; END; $$ LANGUAGE plpgsql",
                f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}",
                f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW "
                f"EXECUTE FUNCTION {table}_append_only()"]
    return []


def drop_trigger_statements(table: str, dialect: str) -> list[str]:
    """What the DB OWNER runs to tamper (scripts/tamper.py); the application never does."""
    if dialect == "sqlite":
        return [f"DROP TRIGGER IF EXISTS {table}_no_{verb}" for verb in ("update", "delete")]
    if dialect == "postgresql":
        return [f"ALTER TABLE {table} DISABLE TRIGGER {table}_append_only"]
    return []


def install_triggers(connection, table: str) -> None:
    for sql in trigger_statements(table, connection.dialect.name):
        connection.exec_driver_sql(sql)


for _t in ("audit_events", "audit_checkpoints"):
    event.listen(Base.metadata.tables[_t], "after_create",
                 lambda target, connection, **kw: install_triggers(connection, target.name))
