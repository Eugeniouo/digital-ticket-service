default:
  @just --list

serve:
    uv sync --locked
    uv run -m query_service

up:
    docker compose up -d --wait db

down:
    docker compose down -v

env:
    test -f .env || cp .env.example .env

bootstrap:
    just env
    uv run -m query_service.bootstrap_staff

seed:
    just env
    uv run -m query_service.seed_demo

run:
    just env
    just up
    uv run alembic upgrade head
    just bootstrap
    just serve


fresh:
    just env
    just down
    just up
    uv run alembic upgrade head
    just bootstrap


generate_migrations message:
    just fresh
    uv run alembic revision --autogenerate -m "{{message}}"

test:
    just fresh
    uv run pytest
