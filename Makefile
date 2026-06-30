.PHONY: fmt lint typecheck test test-int migrate revision worker up down logs check

fmt:
	uv run ruff format app tests

lint:
	uv run ruff check app tests

typecheck:
	uv run mypy app

test:
	uv run pytest -m "unit or api or contract"

test-int:
	uv run pytest -m "integration"

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(msg)"

worker:
	uv run arq app.core.wiring.queue.WorkerSettings

up:
	docker compose up -d

down:
	docker compose down -v

logs:
	docker compose logs -f

check:
	make fmt && make lint && make typecheck && uv run lint-imports && make test && make test-int
