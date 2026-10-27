import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from artemis.audit.ledger import SqlAudit
from artemis.db import Db


@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def ledger():
    db = Db("sqlite://")
    db.reset()
    return SqlAudit(db)


def fill(ledger, n=5):
    for i in range(n):
        ledger.append(f"CASE-{i % 2 + 1:04d}", "GRADED", "agent", {"status": "VERIFIED", "unexplained_paise": i})


@pytest.fixture
def real():
    from artemis.wiring import build_deps
    return build_deps("real")
