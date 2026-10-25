test:
	uv run pytest
test-live:
	uv run pytest -m live
schemas:
	uv run python scripts/export_schemas.py
eval:
	uv run python -m eval.run --runs 3
