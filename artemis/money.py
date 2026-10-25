"""PROVISIONAL (Lane A owns). Integer-paise helpers; no float ever touches money."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

_CLEAN = re.compile(r"[₹,\s]|INR|Rs\.?", re.IGNORECASE)


def to_paise(s: str) -> int:
    """'15,08,000.00' -> 150800000. Strings only; rejects floats and >2 decimals."""
    if not isinstance(s, str):
        raise TypeError("to_paise takes a string, never a float/int")
    try:
        d = Decimal(_CLEAN.sub("", s))
    except InvalidOperation:
        raise ValueError(f"not an amount: {s!r}") from None
    paise = d * 100
    if paise != paise.to_integral_value():
        raise ValueError(f"more than 2 decimal places: {s!r}")
    return int(paise)


def format_inr(paise: int) -> str:
    """150800000 -> '15,08,000' (Indian grouping). Whole rupees drop '.00'."""
    sign, p = ("-", -paise) if paise < 0 else ("", paise)
    rupees, rem = divmod(p, 100)
    head, tail = str(rupees)[:-3], str(rupees)[-3:]
    if head:
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        parts.insert(0, head)
        tail = ",".join(parts) + "," + tail
    return f"{sign}{tail}" + (f".{rem:02d}" if rem else "")


def quarter_of(d: date) -> int:
    """Indian financial quarter: Apr-Jun = 1 ... Jan-Mar = 4."""
    return ((d.month - 4) % 12) // 3 + 1
