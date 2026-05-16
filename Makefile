.PHONY: up down logs test migrate shell lint prod

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

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
