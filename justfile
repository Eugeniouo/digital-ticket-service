default:
  @just --list

serve:
    uv sync --locked
    uv run -m query_service

up:
    docker compose up -d --wait db

down:
    docker compose down -v

run:
    just up
    uv run alembic upgrade head
    just serve


fresh:
    just down
    just up
    uv run alembic upgrade head


generate_migrations message:
    just fresh
    uv run alembic revision --autogenerate -m "{{message}}"

test:
    just fresh
    uv run pytest
