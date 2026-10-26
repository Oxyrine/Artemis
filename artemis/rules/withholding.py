"""compute_withholding: expected TDS from the versioned rule table. Integer paise only. It never decides whether
TDS applies beyond the customer's configured flag."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from artemis.db import Customer, Invoice
from artemis.models import CoreError

RULES_FILE = Path(__file__).with_name("tds_rules.yaml")


@lru_cache(maxsize=1)
def _rules() -> tuple[dict, ...]:
    return tuple(yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))["rules"])


def select_rule(category: str, on: str) -> dict:
    """The rule in force for the category on an ISO date (effective_to inclusive, null = open-ended)."""
    for r in _rules():
        if r["category"] == category and str(r["effective_from"]) <= on and (r["effective_to"] is None
                                                                            or on <= str(r["effective_to"])):
            return r
    raise CoreError("not_found", f"no TDS rule for category {category!r} on {on}")


def compute(customer: Customer, invoices: list[Invoice], transaction_date: str) -> dict:
    rule = select_rule(customer.tds_category, transaction_date)
    base = sum(i.taxable_value for i in invoices)
    rate = (rule["rate_bp"] if rule["rate_bp"] is not None else customer.tds_rate_bp) if customer.tds_applicable else 0
    expected = (base * rate + 5000) // 10_000  # basis points, rounded half up to the paisa
    if rule.get("threshold_paise") and base < rule["threshold_paise"]:
        expected = 0
    return {"expected_paise": expected, "base_paise": base, "rate_bp": rate, "rule_ref": rule["rule_ref"],
            "rule_version": str(rule["rule_version"])}
