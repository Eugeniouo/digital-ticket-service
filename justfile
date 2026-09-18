default:
  @just --list

serve:
    uv sync --locked
    uv run -m query_service

up:
    docker compose up -d --wait db

run:
    just up
    uv run alembic upgrade head
    just serve

down:
    docker compose down -v

generate_migrations message:
    just down
    just up
    uv run alembic upgrade head
    uv run alembic revision --autogenerate -m "{{message}}"
