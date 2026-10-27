"""Run the API (and the built UI, if web/dist exists): python -m scripts.serve   [HOST, PORT, DATABASE_URL, ...]
Single worker on purpose: batch and run state live in the process."""
import os
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    os.chdir(ROOT)  # relative paths (data/, runs/, exports/) resolve against the repo whatever the caller's cwd
    # a file database, so a second process (scripts/tamper.py in the live demo) edits the one the server verifies
    os.environ.setdefault("DATABASE_URL", "sqlite:///data/artemis.db")
    uvicorn.run("artemis.api.main:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")),
                app_dir=str(ROOT), log_level="info")
