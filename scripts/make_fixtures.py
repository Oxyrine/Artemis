"""Writes fixtures/case_*.json + fixtures/cases_truth.json (PROVISIONAL stand-in for Lane A's env).
Money is integer paise. Re-running is byte-identical."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "fixtures"
R = 100  # paise per rupee


def case(n, case_id, utr, cust_id, name, payer_raw, inv_nums, tc_amount, status, state, email_extra=""):
    t1, t2 = 1_000_000 * R, 300_000 * R  # taxable 10,00,000 and 3,00,000
    invs = []
    for num, taxable in zip(inv_nums, (t1, t2), strict=True):
        gst = taxable * 18 // 100
        invs.append({"id": f"INV-{num}", "customer_id": cust_id, "invoice_date": "2026-08-04",
                     "due_date": "2026-09-03", "taxable_value": taxable, "gst_amount": gst,
                     "gross_amount": taxable + gst, "po_ref": f"PO-{num}", "status": "open"})
    received = 1_508_000 * R
    refs = " and ".join(i["id"] for i in invs)
    fx = {
        "case_id": case_id, "utr": utr, "customer_id": cust_id,
        "customers": [{"id": cust_id, "legal_name": name, "gstin": f"27ABCDE{n}34F1Z5",
                       "pan": f"ABCDE{n}34F", "tan": f"MUMA{n}345B", "tds_applicable": True,
                       "tds_rate_bp": 200, "tds_category": "contractor"}],
        "invoices": invs,
        "bank_receipts": [{"utr": utr, "value_date": "2026-09-12", "amount": received,
                           "payer_name_raw": payer_raw, "narration": f"NEFT-{utr}-{payer_raw}",
                           "bank_charges": 0, "resolved_customer_id": cust_id}],
        "remittance_emails": [{"id": f"EML-{30 + n:04d}", "received_at": "2026-09-12T10:41:00+05:30",
                               "from_addr": f"accounts@{cust_id.lower()}.example.in",
                               "subject": f"Payment advice {utr}", "customer_id": cust_id,
                               "body_text": f"Dear Sir, payment of Rs 15,08,000 made vide {utr} against "
                                            f"{refs}. TDS deducted @2%.{email_extra} Regards, Accounts"}],
        "tax_credits": ([{"id": f"TC-{18 + n:04d}", "deductor_name": name, "deductor_tan": f"MUMA{n}345B",
                          "our_pan": "AAACO1234Z", "quarter": 2, "amount_credited": tc_amount,
                          "tds_section_ref": "393", "transaction_date": "2026-09-12"}]
                        if tc_amount is not None else []),
        "credit_notes": [],
    }
    truth = {"status": status, "state": state, "is_red_team": status == "CONFLICTING",
             "receipts": [utr], "allocations": [{"invoice_id": i["id"], "amount_paise": i["gross_amount"]}
                                                for i in invs],
             "adjustments": ([{"kind": "tds", "amount_paise": 26_000 * R}] if status != "INSUFFICIENT" else [])}
    return fx, truth


SPECS = [
    (1, "CASE-0007", "UTR839201", "CUST-014", "ABC Infra Private Limited", "ABC INFRA PVT L",
     (1042, 1043), 26_000 * R, "VERIFIED", "PENDING_APPROVAL"),
    (2, "CASE-0008", "UTR839202", "CUST-015", "Delta Build Works Private Limited", "DELTA BUILD WORKS",
     (1052, 1053), None, "PROBABLE", "AWAITING_EVIDENCE"),
    (3, "CASE-0009", "UTR839203", "CUST-016", "Orion Civil Limited", "ORION CIVIL LTD",
     (1062, 1063), 20_000 * R, "CONFLICTING", "NEEDS_REVIEW"),
]

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    truth = {}
    for spec in SPECS:
        fx, tr = case(*spec)
        (OUT / f"case_{fx['utr']}.json").write_text(json.dumps(fx, indent=2, sort_keys=True) + "\n")
        truth[fx["case_id"]] = tr
    (OUT / "cases_truth.json").write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n")
    print("wrote", len(SPECS), "fixtures")
