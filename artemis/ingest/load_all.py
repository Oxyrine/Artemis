"""Loads every file in data/env/ into the database in ONE transaction (POST /reset calls this).
Amounts are read as strings and converted by money.to_paise, never via float. EML bodies are stored as plain
text only: meaning is extracted later by Lane B's parse_remittance. Any validation breach aborts the load."""
from __future__ import annotations

import email
from email import policy
from email.utils import parseaddr
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

from artemis.db import (BankReceipt, Customer, CreditNote, Db, Invoice, RemittanceEmail, Reviewer, TaxCredit)
from artemis.money import to_paise

ENV_DIR = Path(__file__).resolve().parents[2] / "data" / "env"


class LoadError(ValueError):
    """Raised on any validation breach: the transaction rolls back and nothing is loaded."""


def _csv(path: Path) -> list[dict]:
    return pd.read_csv(path, dtype=str, keep_default_na=False).to_dict("records")


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_body(msg) -> str:
    part = msg.get_body(preferencelist=("plain",))
    if part is not None:
        return part.get_content().strip()
    html = msg.get_body(preferencelist=("html",))
    if html is None:
        return ""
    p = _Text()
    p.feed(html.get_content())
    return " ".join("".join(p.parts).split())


def seed_reviewers(s) -> None:
    """Two reviewers: an analyst (limit 10,00,000) and a controller (no limit)."""
    if s.get(Reviewer, "analyst-1") is None:
        s.add_all([Reviewer(id="analyst-1", name="Asha Analyst", role="analyst", approval_limit_paise=10_00_000 * 100),
                   Reviewer(id="controller-1", name="Chandra Controller", role="controller",
                            approval_limit_paise=None)])


def load_all(db: Db, env_dir: Path | str = ENV_DIR) -> dict[str, int]:
    env = Path(env_dir)
    with db.tx() as s:
        customers = _csv(env / "customers.csv")
        for c in customers:
            s.add(Customer(id=c["id"], legal_name=c["legal_name"], gstin=c["gstin"], pan=c["pan"], tan=c["tan"],
                           contact_domain=c["contact_domain"], tds_applicable=c["tds_applicable"] == "Y",
                           tds_rate_bp=int(c["tds_rate_bp"]), tds_category=c["tds_category"]))
        s.flush()
        by_domain = {c["contact_domain"]: c["id"] for c in customers if c["contact_domain"]}

        invs = pd.read_excel(env / "erp_invoices.xlsx", dtype=str, keep_default_na=False).to_dict("records")
        for r in invs:
            taxable, gst, gross = to_paise(r["taxable_value"]), to_paise(r["gst_18pct"]), to_paise(r["gross"])
            if gross != taxable + gst:
                raise LoadError(f"{r['invoice_no']}: gross {gross} != taxable {taxable} + GST {gst}")
            s.add(Invoice(id=r["invoice_no"], customer_id=r["customer_id"], invoice_date=r["invoice_date"],
                          due_date=r["due_date"], taxable_value=taxable, gst_amount=gst, gross_amount=gross,
                          po_ref=r["po_ref"], status=r["status"]))
        s.flush()  # no relationship() links the mappers, so insert order is ours to keep (Postgres enforces the FKs)

        seen: set[str] = set()
        bank = _csv(env / "bank_statement.csv")
        for r in bank:
            if r["utr"] in seen:
                raise LoadError(f"duplicate UTR {r['utr']}")
            seen.add(r["utr"])
            s.add(BankReceipt(utr=r["utr"], value_date=r["value_date"], amount=to_paise(r["amount"]),
                              payer_name_raw=r["payer_name"], narration=r["narration"],
                              bank_charges=to_paise(r["bank_charges"] or "0")))

        emls = sorted((env / "emails").glob("*.eml"))
        for f in emls:
            with f.open("rb") as fh:
                msg = email.message_from_binary_file(fh, policy=policy.default)
            sender = parseaddr(str(msg["From"]))[1]
            s.add(RemittanceEmail(id=f.stem, received_at=email.utils.parsedate_to_datetime(str(msg["Date"])).isoformat(),
                                  from_addr=sender, subject=str(msg["Subject"]), body_text=_plain_body(msg),
                                  raw_path=f"emails/{f.name}", customer_id=by_domain.get(sender.split("@")[-1])))

        tax = _csv(env / "tax_credit_extract.csv")
        for r in tax:
            if not r["quarter"]:
                raise LoadError(f"tax credit {r['id']} has no quarter")
            s.add(TaxCredit(id=r["id"], deductor_name=r["deductor_name"], deductor_tan=r["deductor_tan"],
                            our_pan=r["our_pan"], quarter=int(r["quarter"]), amount_credited=to_paise(r["amount_credited"]),
                            tds_section_ref=r["section"], transaction_date=r["transaction_date"]))

        cns = _csv(env / "credit_notes.csv")
        for r in cns:  # ERP-issued only; email-only credit notes exist solely in the .eml files
            s.add(CreditNote(id=r["id"], customer_id=r["customer_id"], invoice_id=r["invoice_id"],
                             amount=to_paise(r["amount"]), issued_on=r["issued_on"], source="erp", status="issued"))
        seed_reviewers(s)
        s.flush()
    return {"customers": len(customers), "invoices": len(invs), "bank_receipts": len(bank), "emails": len(emls),
            "tax_credits": len(tax), "credit_notes": len(cns)}
