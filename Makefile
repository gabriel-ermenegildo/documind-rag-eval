# Recipes are single plain commands on purpose: GNU make runs them with cmd.exe on Windows
# and with sh on Linux/CI, so nothing here may depend on shell-specific syntax.

.PHONY: up down migrate dev test lint

# Start Postgres and wait for its healthcheck, so `make migrate` can run right after.
up:
	docker compose up -d --wait

# Stop Postgres. Data stays in the named volume.
down:
	docker compose down

# Apply database migrations.
migrate:
	uv run alembic upgrade head

# Run the API with reload on http://localhost:8000 (Swagger at /docs).
dev:
	uv run uvicorn documind.api.main:app --reload --reload-dir src --port 8000

# Run the test suite. Integration tests need `make up`.
test:
	uv run pytest

# Check lint rules and formatting without changing files.
lint:
	uv run ruff check .
	uv run ruff format --check .
