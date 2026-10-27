"""Builds the synthetic Indian AR environment deterministically (fixed seed) into data/env/ and writes the
answer key to data/cases_truth.json. Re-running produces byte-identical files.

    uv run python -m data.generator.generate

Amounts in the files are rupee strings (never floats); ingestion converts them with money.to_paise.
Case ids are assigned by sorting case groups on their lowest UTR, exactly as matching.matcher does."""
from __future__ import annotations

import csv
import io
import json
import random
import re
import zipfile
from datetime import date, datetime, timedelta
from email import policy
from email.message import EmailMessage
from pathlib import Path

from openpyxl import Workbook
from rapidfuzz import fuzz

from artemis.matching.names import normalize_name
from artemis.money import format_inr, quarter_of

SEED = 20261025
ROOT = Path(__file__).resolve().parents[1]
ENV, TRUTH = ROOT / "env", ROOT / "cases_truth.json"
R = 100  # paise per rupee
TDS_BP = 200

# (id, legal name, email domain, tds_applicable). Ids 014-016 are the hero case and its two twins.
CUSTOMERS = [
    ("CUST-001", "Sunrise Textiles Private Limited", "sunrisetextiles.example.in", True),
    ("CUST-002", "Bharat Logistics Limited", "bharatlogistics.example.in", True),
    ("CUST-003", "Kaveri Agro Foods Private Limited", "kaveriagro.example.in", False),
    ("CUST-004", "Metro Steel Industries Limited", "metrosteel.example.in", True),
    ("CUST-005", "Lotus Pharma Private Limited", "lotuspharma.example.in", False),
    ("CUST-006", "Ganga Polymers LLP", "gangapolymers.example.in", True),
    ("CUST-007", "Zenith Electricals Private Limited", "zenithelectricals.example.in", True),
    ("CUST-008", "Orchid Hospitality Private Limited", "orchidhospitality.example.in", False),
    ("CUST-009", "Himalaya Paper Mills Limited", "himalayapaper.example.in", True),
    ("CUST-010", "Coastal Marine Services Private Limited", "coastalmarine.example.in", True),
    ("CUST-011", "Vertex Software Solutions Private Limited", "vertexsoft.example.in", False),
    ("CUST-012", "Pinnacle Cement Company Limited", "pinnaclecement.example.in", True),
    ("CUST-014", "ABC Infra Private Limited", "abcinfra.example.in", True),
    ("CUST-015", "Delta Build Works Private Limited", "deltabuild.example.in", True),
    ("CUST-016", "Orion Civil Limited", "orioncivil.example.in", True),
]
# Medium-confidence payer strings (fuzzy score 80-94); asserted against the real resolver in tests.
MEDIUM_PAYERS = {"CUST-004": "METRO STEEL INDUSTRY", "CUST-009": "HIMALAYA PAPER MFG"}
OUR_PAN = "AAACO1234Z"


def rupees(paise: int) -> str:
    return f"{paise // R}.{paise % R:02d}"


def bank_name(legal: str) -> str:
    """The payer as an Indian bank statement prints it: upper-case, abbreviated, truncated. The truncation is chosen
    so the resolver still scores it >= 97 (scenarios 1-2 must resolve; scenario 3 uses MEDIUM_PAYERS instead)."""
    full = legal.upper().replace("PRIVATE LIMITED", "PVT LTD").replace(" LIMITED", " LTD")
    if legal.startswith("ABC"):
        return full[:15]  # "ABC INFRA PVT L", the spec's example
    for w in range(18, 9, -1):
        cand = full[:w].rstrip()
        if fuzz.token_set_ratio(normalize_name(cand), normalize_name(legal)) >= 97:
            return cand
    return full


class Env:
    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.cust = {c[0]: c for c in CUSTOMERS}
        self.invoices: dict[str, dict] = {}
        self.receipts: list[dict] = []
        self.emails: list[dict] = []
        self.tax_credits: list[dict] = []
        self.credit_notes: list[dict] = []
        self.groups: list[dict] = []  # one per case: truth entry + its UTRs
        self._utr, self._inv, self._eml, self._tc, self._cn = 839195, 1100, 0, 0, 0
        self.grosses: set[int] = set()

    # ---- ids
    def utr(self) -> str:
        self._utr += 1
        return f"UTR{self._utr - 1}"

    def inv_id(self) -> str:
        while True:
            self._inv += 1
            if f"INV-{self._inv}" not in self.invoices and self._inv not in (1042, 1043, 1052, 1053, 1062, 1063):
                return f"INV-{self._inv}"

    # ---- rows
    def invoice(self, cust: str, taxable_rupees: int | None = None, *, id: str | None = None,
                inv_date: date | None = None, status: str = "open", net_days: int = 30, dup_ok: bool = False) -> dict:
        while True:
            t = (taxable_rupees if taxable_rupees is not None else self.rng.randrange(60, 900) * 1000) * R
            gross = t + t * 18 // 100
            if dup_ok or gross not in self.grosses:
                break
            taxable_rupees = None  # collision: redraw
        self.grosses.add(gross)
        d = inv_date or date(2026, 7, 5) + timedelta(days=self.rng.randrange(0, 31))
        row = {"id": id or self.inv_id(), "customer_id": cust, "invoice_date": d.isoformat(),
               "due_date": (d + timedelta(days=net_days)).isoformat(), "taxable_value": t,
               "gst_amount": t * 18 // 100, "gross_amount": gross, "status": status}
        row["po_ref"] = "PO-" + row["id"][4:]
        self.invoices[row["id"]] = row
        return row

    def receipt(self, cust: str, amount: int, value_date: date, *, payer: str | None = None, refs=(),
                utr: str | None = None, charges: int = 0, extra: str = "") -> dict:
        utr = utr or self.utr()
        payer = payer or bank_name(self.cust[cust][1])
        mode = self.rng.choice(["NEFT", "RTGS", "IMPS"]) if amount >= 20_000_000 else self.rng.choice(["NEFT", "IMPS"])
        narration = "/".join([mode, utr, payer, *refs] + ([extra] if extra else []))
        row = {"value_date": value_date.isoformat(), "utr": utr, "amount": amount, "payer_name_raw": payer,
               "narration": narration, "bank_charges": charges}
        self.receipts.append(row)
        return row

    def pay_date(self, inv: dict, lo: int = 20, hi: int = 55) -> date:
        d = date.fromisoformat(inv["invoice_date"]) + timedelta(days=self.rng.randrange(lo, hi))
        return min(d, date(2026, 9, 30))

    def email(self, cust: str, subject: str, body: str, when: date, *, quoted: str = "") -> str:
        self._eml += 1
        eid = f"EML-{self._eml:04d}"
        self.emails.append({"id": eid, "customer_id": cust, "subject": subject, "body": body, "quoted": quoted,
                            "from": f"accounts@{self.cust[cust][2]}", "date": when})
        return eid

    def tax_credit(self, cust: str, amount: int, tx_date: date) -> None:
        self._tc += 1
        self.tax_credits.append({"id": f"TC-{self._tc:04d}", "deductor_name": self.cust[cust][1],
                                 "deductor_tan": tan(cust), "our_pan": OUR_PAN, "quarter": quarter_of(tx_date),
                                 "amount_credited": amount, "tds_section_ref": "393" if tx_date >= date(2026, 4, 1)
                                 else "194C", "transaction_date": tx_date.isoformat()})

    def credit_note(self, cust: str, inv: dict, amount: int, on: date) -> str:
        self._cn += 1
        cid = f"CN-{self._cn:04d}"
        self.credit_notes.append({"id": cid, "customer_id": cust, "invoice_id": inv["id"], "amount": amount,
                                  "issued_on": on.isoformat(), "source": "erp", "status": "issued"})
        return cid

    def case(self, status: str, receipts: list[dict], invs: list[dict], adjustments: list[tuple[str, int]], *,
             red_team: bool = False, allocate: bool = True) -> None:
        state = {"AUTO_CLOSED": "AUTO_CLOSED", "VERIFIED": "PENDING_APPROVAL", "PROBABLE": "AWAITING_EVIDENCE",
                 "INSUFFICIENT": "NEEDS_REVIEW", "CONFLICTING": "NEEDS_REVIEW"}[status]
        self.groups.append({"status": status, "state": state, "is_red_team": red_team,
                            "receipts": [r["utr"] for r in receipts],
                            "allocations": [{"invoice_id": i["id"], "amount_paise": i["gross_amount"]}
                                            for i in invs] if allocate else [],
                            "adjustments": [{"kind": k, "amount_paise": a} for k, a in adjustments]})


def tan(cust: str) -> str:
    return f"MUMX{int(cust[5:]):05d}B"


def pan(cust: str) -> str:
    return f"AAAC{chr(64 + int(cust[5:]) % 26 + 1)}{int(cust[5:]):04d}K"


SPECIAL = {"CUST-014", "CUST-015", "CUST-016"} | set(MEDIUM_PAYERS)  # hero + twins; medium-confidence payers
# The two medium-confidence customers appear nowhere else: the matcher learns an alias from every resolved payer, so
# another receipt from them could teach it a closer spelling and quietly turn scenario 3 into an auto-close.


def tds_customers(e: Env) -> list[str]:
    return [c[0] for c in CUSTOMERS if c[3] and c[0] not in SPECIAL]


def tds_case(e: Env, cust: str, n_inv: int, *, credit: str, utr: str | None = None, ids=(), when: date | None = None,
             inv_date: date | None = None, taxes: tuple[int, ...] | None = None) -> tuple:
    """Receipt = gross of n invoices minus 2% TDS on the taxable value. credit: 'equal'|'none'|'other'."""
    invs = [e.invoice(cust, (taxes[i] if taxes else None), id=(ids[i] if i < len(ids) else None), inv_date=inv_date,
                  dup_ok=bool(taxes))  # the twins deliberately repeat the hero's amounts
            for i in range(n_inv)]
    tds = sum(i["taxable_value"] for i in invs) * TDS_BP // 10_000
    vd = when or e.pay_date(invs[0], 35, 58)
    rc = e.receipt(cust, sum(i["gross_amount"] for i in invs) - tds, vd, utr=utr, refs=[i["id"] for i in invs])
    refs = " and ".join(i["id"] for i in invs)
    body = (f"Dear Sir, please find payment of Rs {format_inr(rc['amount'])} made vide {rc['utr']} against {refs}. "
            f"TDS deducted @2% on the taxable value. Regards, Accounts")
    e.email(cust, f"Payment advice {rc['utr']}", body, vd)
    if credit == "equal":
        e.tax_credit(cust, tds, vd)
    elif credit == "other":
        e.tax_credit(cust, tds - 6_000 * R, vd)
    return rc, invs, tds


def build() -> Env:
    e = Env()
    rng = e.rng
    plain = [c[0] for c in CUSTOMERS if c[0] not in SPECIAL]

    def exact(n: int) -> None:  # scenario 1 (and 2 with alias): amount, customer and invoice ref all agree
        for _ in range(n):
            cust = rng.choice(plain)
            inv = e.invoice(cust)
            rc = e.receipt(cust, inv["gross_amount"], e.pay_date(inv), refs=[inv["id"]])
            e.case("AUTO_CLOSED", [rc], [inv], [])

    exact(6)  # CASE-0001..0006
    # hero (CASE-0007) and its twins (CASE-0008 no tax credit, CASE-0009 different amount)
    d = date(2026, 8, 4)
    tds_case(e, "CUST-014", 2, credit="equal", utr="UTR839201", ids=("INV-1042", "INV-1043"), when=date(2026, 9, 12),
             inv_date=d, taxes=(1_000_000, 300_000))
    e.case("VERIFIED", [e.receipts[-1]], [e.invoices["INV-1042"], e.invoices["INV-1043"]], [("tds", 26_000 * R)])
    tds_case(e, "CUST-015", 2, credit="none", utr="UTR839202", ids=("INV-1052", "INV-1053"), when=date(2026, 9, 12),
             inv_date=d, taxes=(1_000_000, 300_000))
    e.case("PROBABLE", [e.receipts[-1]], [e.invoices["INV-1052"], e.invoices["INV-1053"]], [("tds", 26_000 * R)])
    rc, invs, tds = tds_case(e, "CUST-016", 2, credit="none", utr="UTR839203", ids=("INV-1062", "INV-1063"),
                             when=date(2026, 9, 12), inv_date=d, taxes=(1_000_000, 300_000))
    e.tax_credit("CUST-016", 20_000 * R, date(2026, 9, 12))  # R3: tax credit shows 20,000 against 26,000
    e.case("CONFLICTING", [rc], invs, [("tds", tds)], red_team=True)
    e._utr = 839204  # hero + twins used explicit UTRs 839201-839203

    exact(2)  # rest of scenario 1 (8 in total)
    for _ in range(2):  # 2: alias, high confidence (truncated name, or GSTIN in the narration)
        cust = rng.choice(plain)
        inv = e.invoice(cust)
        gst = f"27{pan(cust)}1Z5"
        rc = e.receipt(cust, inv["gross_amount"], e.pay_date(inv), refs=[inv["id"]], extra=gst)
        e.case("AUTO_CLOSED", [rc], [inv], [])
    for cust, alias in MEDIUM_PAYERS.items():  # 3: alias, medium confidence -> investigated, VERIFIED
        inv = e.invoice(cust)
        rc = e.receipt(cust, inv["gross_amount"], e.pay_date(inv), payer=alias, refs=[inv["id"]])
        e.case("VERIFIED", [rc], [inv], [])
    # 4: TDS with equal tax credit (3 more; the third is the legacy pre-April-2026 invoice)
    for cust in rng.sample(tds_customers(e), 2):
        rc, invs, tds = tds_case(e, cust, rng.choice([1, 2]), credit="equal")
        e.case("VERIFIED", [rc], invs, [("tds", tds)])
    legacy = [c for c in tds_customers(e)][-1]
    rc, invs, tds = tds_case(e, legacy, 1, credit="equal", when=date(2026, 3, 20), inv_date=date(2026, 2, 20))
    e.case("VERIFIED", [rc], invs, [("tds", tds)])
    # 5: TDS plus an ERP-issued credit note on the same receipt
    cust = tds_customers(e)[3]
    inv = e.invoice(cust)
    tds = inv["taxable_value"] * TDS_BP // 10_000 - 0
    cn_amt = 25_000 * R
    vd = e.pay_date(inv, 35, 58)
    cn = e.credit_note(cust, inv, cn_amt, vd - timedelta(days=10))
    rc = e.receipt(cust, inv["gross_amount"] - tds - cn_amt, vd, refs=[inv["id"]])
    e.email(cust, f"Payment advice {rc['utr']}", f"Dear Sir, payment of Rs {format_inr(rc['amount'])} vide {rc['utr']} "
            f"against {inv['id']} after TDS and credit note {cn}. Regards, Accounts", vd)
    e.tax_credit(cust, tds, vd)
    e.case("VERIFIED", [rc], [inv], [("tds", tds), ("credit_note", cn_amt)])
    # 6: TDS deducted, tax credit not yet filed (2 more; the twin is CASE-0008)
    for cust in rng.sample(tds_customers(e), 2):
        rc, invs, tds = tds_case(e, cust, 1, credit="none")
        e.case("PROBABLE", [rc], invs, [("tds", tds)])
    # 7: TDS deducted, tax credit shows a different amount (1 more; the twin is CASE-0009)
    cust = tds_customers(e)[5]
    rc, invs, tds = tds_case(e, cust, 1, credit="other")
    e.case("CONFLICTING", [rc], invs, [("tds", tds)], red_team=True)
    # 8: one UTR paying two or three invoices, no deductions
    for n in (2, 3):
        cust = rng.choice(plain)
        invs = [e.invoice(cust) for _ in range(n)]
        vd = e.pay_date(invs[-1], 22, 50)
        rc = e.receipt(cust, sum(i["gross_amount"] for i in invs), vd, refs=[i["id"] for i in invs])
        e.email(cust, f"Remittance {rc['utr']}", f"Dear Sir, we have remitted Rs {format_inr(rc['amount'])} "
                f"vide {rc['utr']} towards {', '.join(i['id'] for i in invs)}. Regards, Accounts", vd)
        e.case("VERIFIED", [rc], invs, [])
    # 9: two UTRs paying one invoice (one case, two receipts)
    for _ in range(2):
        cust = rng.choice(plain)
        inv = e.invoice(cust)
        first = (inv["gross_amount"] // (2 * R)) * R
        vd = e.pay_date(inv, 20, 40)
        r1 = e.receipt(cust, first, vd, refs=[inv["id"]])
        r2 = e.receipt(cust, inv["gross_amount"] - first, vd + timedelta(days=4), refs=[inv["id"]])
        e.case("VERIFIED", [r1, r2], [inv], [])
    # 10: credit note agreed only in email, not issued in the ERP
    for _ in range(3):
        cust = rng.choice(plain)
        inv = e.invoice(cust)
        cn_amt = rng.randrange(10, 40) * 1000 * R
        vd = e.pay_date(inv, 25, 50)
        rc = e.receipt(cust, inv["gross_amount"] - cn_amt, vd, refs=[inv["id"]])
        e.email(cust, f"Re: Credit note for {inv['id']}", f"Dear Sir, as agreed we are paying Rs "
                f"{format_inr(rc['amount'])} vide {rc['utr']} for {inv['id']}, net of the agreed credit note of Rs "
                f"{format_inr(cn_amt)} (to be issued). Regards, Accounts", vd,
                quoted="On Tue, you wrote: > We will raise the credit note in the next billing cycle.")
        e.case("PROBABLE", [rc], [inv], [("credit_note", cn_amt)])
    # 11: credit note issued in the ERP
    cust = rng.choice(plain)
    inv = e.invoice(cust)
    cn_amt = 18_000 * R
    vd = e.pay_date(inv, 25, 50)
    cn = e.credit_note(cust, inv, cn_amt, vd - timedelta(days=12))
    rc = e.receipt(cust, inv["gross_amount"] - cn_amt, vd, refs=[inv["id"]])
    e.case("VERIFIED", [rc], [inv], [("credit_note", cn_amt)])
    # 12: payment lands after month-end, outside the matcher's date window
    for _ in range(2):
        cust = rng.choice(plain)
        inv = e.invoice(cust, inv_date=date(2026, 7, 2), net_days=10)
        rc = e.receipt(cust, inv["gross_amount"], date(2026, 9, 18 + rng.randrange(0, 8)), refs=[inv["id"]])
        e.case("VERIFIED", [rc], [inv], [])
    # 13: bank charges shown on the statement line
    cust = rng.choice(plain)
    inv = e.invoice(cust)
    rc = e.receipt(cust, inv["gross_amount"] - 590 * R, e.pay_date(inv), refs=[inv["id"]], charges=590 * R)
    e.case("VERIFIED", [rc], [inv], [("bank_charge", 590 * R)])
    # 14: rounding short by 50 paise
    cust = rng.choice(plain)
    inv = e.invoice(cust)
    rc = e.receipt(cust, inv["gross_amount"] - 50, e.pay_date(inv), refs=[inv["id"]])
    e.case("VERIFIED", [rc], [inv], [("rounding", 50)])
    # 15: genuinely unexplained short payment
    for _ in range(3):
        cust = rng.choice(plain)
        inv = e.invoice(cust)
        rc = e.receipt(cust, inv["gross_amount"] - rng.randrange(12, 60) * 1000 * R - 37 * R, e.pay_date(inv),
                       refs=[inv["id"]])
        e.case("INSUFFICIENT", [rc], [inv], [])
    # 16: R1 email says "paid in full in two transfers" but only one transfer exists
    cust = rng.choice(plain)
    inv = e.invoice(cust)
    vd = e.pay_date(inv, 25, 50)
    rc = e.receipt(cust, (inv["gross_amount"] // (2 * R)) * R, vd, refs=[inv["id"]])
    ghost = "UTR" + str(e._utr + 400)
    e.email(cust, f"Payment for {inv['id']}", f"Dear Sir, {inv['id']} has been paid in full in two transfers: "
            f"{rc['utr']} and {ghost}. Regards, Accounts", vd)
    e.case("CONFLICTING", [rc], [inv], [], red_team=True)
    # 17: R2 narration cites another customer's invoice; the payer owns INV-2210 for the same amount
    a, b = rng.sample(plain, 2)
    other = e.invoice(b, id="INV-2201")
    own = e.invoice(a, other["taxable_value"] // R, id="INV-2210", dup_ok=True)  # same amount, different owner
    rc = e.receipt(a, own["gross_amount"], e.pay_date(own), refs=["INV-2201"])
    e.case("CONFLICTING", [rc], [own], [], red_team=True)
    # 18: R4 duplicate payment of an invoice already applied
    cust = rng.choice(plain)
    inv = e.invoice(cust, status="applied")
    rc = e.receipt(cust, inv["gross_amount"], e.pay_date(inv, 45, 58), refs=[inv["id"]])
    e.case("INSUFFICIENT", [rc], [inv], [], red_team=True, allocate=False)

    # filler open invoices (up to ~70), unrelated amounts, never equal to a receipt
    while len(e.invoices) < 70:
        e.invoice(rng.choice(plain))
    # distractor emails (replies about unrelated invoices) to reach ~25
    while len(e.emails) < 25:
        cust = rng.choice(plain)
        o = rng.choice([i for i in e.invoices.values() if i["customer_id"] == cust] or [None])
        if o:
            e.email(cust, f"Query on {o['id']}", f"Dear Sir, please confirm the PO reference for {o['id']}. "
                    "Regards, Accounts", date(2026, 8, 20) + timedelta(days=len(e.emails)))
    # noise rows in the tax-credit extract from deductors we are not reconciling
    for k in range(5):  # other deductors paying us on other dates: noise, never one of our reconciliation customers
        e._tc += 1
        e.tax_credits.append({"id": f"TC-{e._tc:04d}", "deductor_name": f"External Deductor {k + 1} Pvt Ltd",
                              "deductor_tan": f"DELX{k + 1:05d}C", "our_pan": OUR_PAN, "quarter": 2,
                              "amount_credited": rng.randrange(5, 40) * 1000 * R + 13,
                              "tds_section_ref": "393", "transaction_date": date(2026, 8, 10 + k).isoformat()})
    return e


# ---------------------------------------------------------------- writers
def _csv(path: Path, header: list[str], rows: list[list]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    path.write_bytes(buf.getvalue().encode("utf-8"))


def _write_xlsx(path: Path, header: list[str], rows: list[list]) -> None:
    wb = Workbook()
    wb.properties.creator, wb.properties.created, wb.properties.modified = "artemis", datetime(2026, 10, 1), datetime(2026, 10, 1)
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)
    src = zipfile.ZipFile(path)  # zip entries carry the build time: rewrite with a fixed one for byte-identical output
    entries = [(i.filename, src.read(i.filename)) for i in src.infolist()]
    src.close()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as out:  # stored, not deflated: deflate bytes vary with the zlib build
        for name, data in entries:
            if name == "docProps/core.xml":  # openpyxl stamps 'modified' with the current time on save
                data = re.sub(rb"(<dcterms:modified[^>]*>)[^<]*", rb"\g<1>2026-10-01T00:00:00Z", data)
            zi = zipfile.ZipInfo(name, (2026, 10, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_STORED
            out.writestr(zi, data)


def _eml(row: dict) -> bytes:
    m = EmailMessage(policy=policy.SMTP)
    m["From"], m["To"] = f"Accounts <{row['from']}>", "ar@ourcompany.example.in"
    m["Subject"], m["Message-ID"] = row["subject"], f"<{row['id'].lower()}@artemis.example.in>"
    m["Date"] = f"{row['date']:%a, %d %b %Y} 10:41:00 +0530"
    text = row["body"] + (f"\n\n{row['quoted']}" if row["quoted"] else "")
    m.set_content(text)
    m.add_alternative("<html><body><p>" + row["body"] + "</p></body></html>", subtype="html")
    m.set_boundary(f"===artemis-{row['id'].lower()}===")
    return m.as_bytes()


def write(e: Env) -> dict:
    ENV.mkdir(parents=True, exist_ok=True)
    (ENV / "emails").mkdir(exist_ok=True)
    _csv(ENV / "customers.csv", ["id", "legal_name", "gstin", "pan", "tan", "contact_domain", "tds_applicable",
                                  "tds_rate_bp", "tds_category"],
         [[c[0], c[1], f"27{pan(c[0])}1Z5", pan(c[0]), tan(c[0]), c[2], "Y" if c[3] else "N",
           TDS_BP if c[3] else 0, "contractor"] for c in CUSTOMERS])
    _write_xlsx(ENV / "erp_invoices.xlsx",
                ["invoice_no", "customer_id", "invoice_date", "due_date", "taxable_value", "gst_18pct", "gross",
                 "po_ref", "status"],
                [[i["id"], i["customer_id"], i["invoice_date"], i["due_date"], rupees(i["taxable_value"]),
                  rupees(i["gst_amount"]), rupees(i["gross_amount"]), i["po_ref"], i["status"]]
                 for i in sorted(e.invoices.values(), key=lambda i: i["id"])])
    _csv(ENV / "bank_statement.csv", ["value_date", "utr", "amount", "payer_name", "narration", "bank_charges"],
         [[r["value_date"], r["utr"], format_inr(r["amount"]) + (".00" if r["amount"] % R == 0 else ""),
           r["payer_name_raw"], r["narration"], rupees(r["bank_charges"])]
          for r in sorted(e.receipts, key=lambda r: r["utr"])])
    for row in e.emails:
        (ENV / "emails" / f"{row['id']}.eml").write_bytes(_eml(row))
    _csv(ENV / "tax_credit_extract.csv", ["id", "deductor_name", "deductor_tan", "our_pan", "quarter",
                                           "amount_credited", "section", "transaction_date"],
         [[t["id"], t["deductor_name"], t["deductor_tan"], t["our_pan"], t["quarter"], rupees(t["amount_credited"]),
           t["tds_section_ref"], t["transaction_date"]] for t in e.tax_credits])
    _csv(ENV / "credit_notes.csv", ["id", "customer_id", "invoice_id", "amount", "issued_on"],
         [[c["id"], c["customer_id"], c["invoice_id"], rupees(c["amount"]), c["issued_on"]] for c in e.credit_notes])
    # answer key: case ids = order of each group's lowest UTR (the case builder does the same)
    truth = {}
    for n, g in enumerate(sorted(e.groups, key=lambda g: min(g["receipts"])), 1):
        truth[f"CASE-{n:04d}"] = g
    # CRLF written explicitly: write_text would translate \n by platform and the file must be byte-identical everywhere
    TRUTH.write_bytes((json.dumps(truth, indent=2, sort_keys=True) + "\n").replace("\n", "\r\n").encode("utf-8"))
    return truth


def main() -> None:
    e = build()
    truth = write(e)
    split = {s: sum(g["status"] == s for g in truth.values())
             for s in ("AUTO_CLOSED", "VERIFIED", "PROBABLE", "CONFLICTING", "INSUFFICIENT")}
    assert split == {"AUTO_CLOSED": 10, "VERIFIED": 16, "PROBABLE": 6, "CONFLICTING": 4, "INSUFFICIENT": 4}, split
    assert len(truth) == 40 and truth["CASE-0007"]["receipts"] == ["UTR839201"], "hero must be CASE-0007"
    print(f"wrote {len(truth)} cases, {len(e.invoices)} invoices, {len(e.receipts)} bank lines, "
          f"{len(e.emails)} emails, {len(e.tax_credits)} tax rows -> {split}")


if __name__ == "__main__":
    main()
