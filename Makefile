test:
	uv run pytest
test-live:
	uv run --env-file .env pytest -m live -s
schemas:
	uv run python -m scripts.export_schemas
eval:
	uv run --env-file .env python -m eval.run --runs 3
