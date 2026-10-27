"""uvicorn artemis.api.main:app  (single worker: run state lives in the process).
Database: DATABASE_URL (default: an in-memory SQLite, re-seeded on every start)."""
from artemis.api.app import create_app

app = create_app()
