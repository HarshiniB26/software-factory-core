.PHONY: sync lint test format api worker migrate up doctor sandbox-image

sync:
	uv sync --all-packages --group dev

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright
	uv run lint-imports

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

migrate:
	uv run alembic -c packages/core/alembic.ini upgrade head

api:
	uv run factory-api

worker:
	uv run factory-worker

up:
	uv run factory up

doctor:
	uv run factory doctor

sandbox-image:
	docker build -t factory-sandbox:local modules/sandboxes/image
