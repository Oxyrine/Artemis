test:
	uv run pytest
test-live:
	uv run --env-file .env pytest -m live -s
schemas:
	uv run python -m scripts.export_schemas
eval:
	uv run --env-file .env python -m eval.run --runs 3

demo:
	docker compose -f deploy/docker-compose.yml up --build
demo-down:
	docker compose -f deploy/docker-compose.yml down -v
seed:
	uv run python -m scripts.seed
smoke:
	cd web && npm run build && npm run e2e

demo-local:
	cd web && npm ci && npm run build
	uv run python -m scripts.seed
	ARTEMIS_PREPARE=0 uv run python -m scripts.serve
workflow:
	cd web && npm run e2e:workflow
