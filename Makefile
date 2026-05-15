.PHONY: up down logs test migrate shell lint

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose exec api alembic upgrade head

shell:
	docker compose exec api bash

test:
	pytest

lint:
	ruff check app/ tests/
