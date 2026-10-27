"""Writes contracts/openapi.json from the FastAPI app. The UI generates its TypeScript types from this file, and a test
fails when it drifts from the code (`uv run python -m scripts.export_openapi` regenerates it)."""
import json
from pathlib import Path

from artemis.api.app import create_app
from artemis.wiring import build_deps

OUT = Path(__file__).resolve().parent.parent / "contracts" / "openapi.json"


def spec() -> dict:
    return create_app(build_deps("real", prepare=False)).openapi()


if __name__ == "__main__":
    OUT.write_text(json.dumps(spec(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", OUT)
