"""Name normalization and entity resolution (Lane A, no LLM). GSTIN/PAN in the narration is a certain match;
otherwise RapidFuzz token_set_ratio against legal names and known aliases."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from artemis.db import Customer, CustomerAlias

RESOLVED, CANDIDATE = 95, 80  # >=95 resolved; 80-94 candidates handed to the agent; <80 unresolved
_SUFFIXES = {"PVT", "PRIVATE", "LTD", "LIMITED", "LLP", "CO", "AND"}
_ABBREV = {"INDS": "INDUSTRIES", "SVCS": "SERVICES", "MFG": "MANUFACTURING", "INTL": "INTERNATIONAL",
           "ENGG": "ENGINEERING", "CORP": "CORPORATION"}
_GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


def normalize_name(s: str) -> str:
    """Upper-case, strip punctuation, collapse spaces, drop company suffixes, expand common abbreviations."""
    words = re.sub(r"[^A-Z0-9 ]", " ", s.upper().replace("&", " AND ")).split()
    return " ".join(_ABBREV.get(w, w) for w in words if w not in _SUFFIXES)


@dataclass
class Resolution:
    customer_id: str | None  # set only when resolved (score >= 95 or GSTIN/PAN)
    score: int
    candidates: list[dict] = field(default_factory=list)  # [{customer_id, legal_name, score}], best first
    via: str = "none"  # gstin | pan | fuzzy | none


def resolve(s: Session, payer_name_raw: str, narration: str = "") -> Resolution:
    text = f"{payer_name_raw} {narration}".upper()
    customers = s.scalars(select(Customer)).all()
    for pattern, attr, via in ((_GSTIN, "gstin", "gstin"), (_PAN, "pan", "pan")):
        for token in pattern.findall(text):
            hit = next((c for c in customers if getattr(c, attr) == token), None)
            if hit:
                return Resolution(hit.id, 100, [{"customer_id": hit.id, "legal_name": hit.legal_name, "score": 100}], via)
    q = normalize_name(payer_name_raw)
    names: dict[str, list[str]] = {c.id: [c.legal_name] for c in customers}
    for a in s.scalars(select(CustomerAlias)):
        names.setdefault(a.customer_id, []).append(a.alias)
    by_id = {c.id: c for c in customers}
    scored = sorted(({"customer_id": cid, "legal_name": by_id[cid].legal_name,
                      "score": max(int(round(fuzz.token_set_ratio(q, normalize_name(n)))) for n in ns)}
                     for cid, ns in names.items()), key=lambda d: (-d["score"], d["customer_id"]))
    cands = [c for c in scored if c["score"] >= CANDIDATE]
    top = cands[0] if cands else None
    tie = len(cands) > 1 and cands[1]["score"] == top["score"]
    if top and top["score"] >= RESOLVED and not tie:
        return Resolution(top["customer_id"], top["score"], cands, "fuzzy")
    return Resolution(None, top["score"] if top else 0, cands, "fuzzy" if top else "none")
