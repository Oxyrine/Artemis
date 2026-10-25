"""Case narrative: a template filled from engine outputs. The LLM may rephrase it, but every figure and id
in the rephrase must already appear in the template, otherwise the template is used."""
from __future__ import annotations

import re

from artemis.money import format_inr
from artemis.models import AllocationResult, Grade

TEMPLATE_VERSION = 1
_ID = re.compile(r"\b[A-Z]{2,4}-?\d+\b")  # INV-1042, UTR839201, EV-0003, TC-0019
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def figures(text: str) -> set[str]:
    """Every invoice/evidence id and every number in the text, normalised (commas and .00 dropped)."""
    ids = set(_ID.findall(text))
    nums = {n.replace(",", "").removesuffix(".00").rstrip(".") for n in _NUM.findall(_ID.sub(" ", text))}
    return ids | nums


def template_narrative(alloc: AllocationResult | None, grade: Grade, rule_refs: list[str],
                       evidence_ids: list[str]) -> str:
    if alloc is None:
        return (f"No allocation could be proposed for this receipt. Grade: {grade.status.value}. "
                "Needs manual review.")
    inv = ", ".join(a.invoice_id for a in alloc.allocations)
    parts = [f"Receipt {', '.join(alloc.utrs)} of INR {format_inr(alloc.received_paise)} was matched to {inv}, "
             f"invoiced INR {format_inr(alloc.invoiced_paise)}; variance INR {format_inr(alloc.variance_paise)}."]
    for a in alloc.adjustments:
        parts.append(f"{a.kind.value} INR {format_inr(a.amount_paise)} "
                     f"{'validated' if a.validated else 'NOT validated'}.")
    if rule_refs:
        parts.append("Rule: " + "; ".join(sorted(set(rule_refs))) + ".")
    parts.append(f"Unexplained INR {format_inr(alloc.unexplained_paise)}. Grade: {grade.status.value}.")
    for f in grade.flags:
        parts.append(f"Contradiction {f.code}: {f.evidence_a} vs {f.evidence_b}.")
    if grade.duplicate:
        parts.append(f"Duplicate payment; {grade.recommendation}.")
    if evidence_ids:
        parts.append("Evidence: " + ", ".join(evidence_ids) + ".")
    return " ".join(parts)


def build_narrative(template: str, llm=None) -> tuple[str, str]:
    """Returns (text, source) with source in {"llm", "template"}."""
    if llm is None:
        return template, "template"
    try:
        resp = llm.chat([{"role": "system", "content": "Rephrase for a finance reviewer in 2-3 sentences. "
                          "Keep every number and id exactly; add none."},
                         {"role": "user", "content": template}])
    except Exception:
        return template, "template"
    text = (resp.text or "").strip()
    return (text, "llm") if text and figures(text) <= figures(template) else (template, "template")
