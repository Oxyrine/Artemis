import json
from pathlib import Path

import pytest

from artemis.models import Evidence
from artemis.wiring import build_deps

TRUTH = json.loads((Path(__file__).resolve().parents[2] / "data" / "cases_truth.json").read_text(encoding="utf-8"))


@pytest.fixture
def real():
    """Fresh Lane A stack: environment loaded, matcher run."""
    return build_deps("real")


@pytest.fixture
def raw():
    """Environment loaded but the matcher NOT run (for tests that tamper with the data first)."""
    d = build_deps("real", prepare=False)
    d.core.reset()
    return d


def evidence(case_id: str, *results) -> list[Evidence]:
    """Evidence rows from CoreResults, the way the tool layer would store them."""
    out, n = [], 0
    for res in results:
        for ref in res.refs:
            n += 1
            out.append(Evidence(id=f"EV-{n:04d}", case_id=case_id, **ref.model_dump()))
    return out


def case_with(status=None, **kw):
    """First truth case matching the filters, e.g. case_with(status='VERIFIED', n_adjustments=2)."""
    for cid, t in TRUTH.items():
        if (status is None or t["status"] == status) and all(
                (len(t[k[2:]]) if k.startswith("n_") else t[k]) == v for k, v in kw.items()):
            return cid
    raise LookupError(kw)
