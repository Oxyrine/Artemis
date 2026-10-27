"""Lane A: SQLAlchemy 2 tables for the deterministic core. Money is integer paise; dates are ISO strings.
Lane B's records (agent runs, tool calls, hypotheses, evidence) live behind ports.RunStore and the audit ledger
is Lane C's, so neither is declared here yet. Types are portable: the same models run on SQLite and Postgres."""
from __future__ import annotations

import os

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # CUST-014
    legal_name: Mapped[str] = mapped_column(String)
    gstin: Mapped[str] = mapped_column(String)
    pan: Mapped[str] = mapped_column(String)
    tan: Mapped[str] = mapped_column(String)
    contact_domain: Mapped[str] = mapped_column(String, default="")  # links remittance emails to a customer
    tds_applicable: Mapped[bool] = mapped_column(Boolean)
    tds_rate_bp: Mapped[int] = mapped_column(Integer)  # basis points: 200 = 2%
    tds_category: Mapped[str] = mapped_column(String)


class CustomerAlias(Base):
    __tablename__ = "customer_aliases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    alias: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)  # bank_narration | email | erp
    confidence: Mapped[int] = mapped_column(Integer)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # INV-1042
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    invoice_date: Mapped[str] = mapped_column(String)
    due_date: Mapped[str] = mapped_column(String)
    taxable_value: Mapped[int] = mapped_column(Integer)
    gst_amount: Mapped[int] = mapped_column(Integer)
    gross_amount: Mapped[int] = mapped_column(Integer)
    po_ref: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="open")  # open | partially_applied | applied


class BankReceipt(Base):
    __tablename__ = "bank_receipts"
    utr: Mapped[str] = mapped_column(String, primary_key=True)
    value_date: Mapped[str] = mapped_column(String)
    amount: Mapped[int] = mapped_column(Integer)
    payer_name_raw: Mapped[str] = mapped_column(String)
    narration: Mapped[str] = mapped_column(String)
    bank_charges: Mapped[int] = mapped_column(Integer, default=0)
    resolved_customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    resolution_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    case_id: Mapped[str | None] = mapped_column(String, nullable=True)


class RemittanceEmail(Base):
    __tablename__ = "remittance_emails"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # EML-0031
    received_at: Mapped[str] = mapped_column(String)
    from_addr: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    body_text: Mapped[str] = mapped_column(Text)
    parsed: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # written by Lane B's parse_remittance
    raw_path: Mapped[str] = mapped_column(String)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)


class CreditNote(Base):
    __tablename__ = "credit_notes"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # CN-0004
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"))
    amount: Mapped[int] = mapped_column(Integer)
    issued_on: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="erp")  # erp | email_only
    status: Mapped[str] = mapped_column(String, default="issued")  # issued | agreed_not_issued


class TaxCredit(Base):
    __tablename__ = "tax_credits"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # TC-0019
    deductor_name: Mapped[str] = mapped_column(String)
    deductor_tan: Mapped[str] = mapped_column(String)
    our_pan: Mapped[str] = mapped_column(String)
    quarter: Mapped[int] = mapped_column(Integer)  # Indian financial quarter 1-4
    amount_credited: Mapped[int] = mapped_column(Integer)
    tds_section_ref: Mapped[str] = mapped_column(String)
    transaction_date: Mapped[str] = mapped_column(String)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # CASE-0007
    utr: Mapped[str] = mapped_column(String)  # primary receipt; others point here via bank_receipts.case_id
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    state: Mapped[str] = mapped_column(String, default="NEW")  # written ONLY by grading.policy
    evidence_status: Mapped[str | None] = mapped_column(String, nullable=True)
    variance_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unexplained_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    merged_into: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_reviewer: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[str] = mapped_column(String, default="")


class Allocation(Base):
    __tablename__ = "allocations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)


class Adjustment(Base):
    __tablename__ = "adjustments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    kind: Mapped[str] = mapped_column(String)  # tds | credit_note | bank_charge | rounding
    amount_paise: Mapped[int] = mapped_column(Integer)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validated_by_rule: Mapped[str] = mapped_column(String, default="")


class Reviewer(Base):
    __tablename__ = "reviewers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)  # analyst | controller
    approval_limit_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = unlimited


def make_engine(url: str | None = None) -> Engine:
    """DATABASE_URL (default: sqlite file under data/). `sqlite://` gives a private in-memory DB for tests."""
    url = url or os.environ.get("DATABASE_URL", "sqlite:///data/artemis.db")
    if url == "sqlite://":  # one shared connection so every session sees the same in-memory DB
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})


def reset(engine: Engine) -> None:
    """Drop and recreate every table (the whole migration story until a hosted DB holds data to keep)."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


class Db:
    """Engine + sessions behind one process-wide lock (the batch runs cases on threads and the in-memory test
    DB shares a single connection). ponytail: one lock; per-call sessions on a real pool once Postgres is live."""

    def __init__(self, url: str | None = None):
        import threading
        from contextvars import ContextVar
        self.engine = make_engine(url)
        self._sessions = session_factory(self.engine)
        self.lock = threading.RLock()
        self._ambient: ContextVar[Session | None] = ContextVar(f"db-session-{id(self)}", default=None)

    def tx(self):
        """One transaction per call, except nested: a tx() opened while another is active in this thread JOINS it, so a
        state change and its audit event (written by the ledger from inside the policy engine) commit or roll back together."""
        from contextlib import contextmanager

        @contextmanager
        def _tx():
            outer = self._ambient.get()
            if outer is not None:
                yield outer
                return
            with self.lock, self._sessions() as s:
                token = self._ambient.set(s)
                try:
                    yield s
                    s.commit()
                except Exception:
                    s.rollback()
                    raise
                finally:
                    self._ambient.reset(token)
        return _tx()

    def reset(self) -> None:
        with self.lock:
            reset(self.engine)
