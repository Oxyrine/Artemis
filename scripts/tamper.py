"""python -m scripts.tamper [seq]  - edit one audit event as the DB owner, then run Verify chain (it goes red)."""
import sys

from artemis.audit.tamper import tamper
from artemis.db import Db

if __name__ == "__main__":
    result = tamper(Db(), int(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(f"tampered with audit event #{result['seq']}: {result['field']} {result['before']} -> {result['after']}")
