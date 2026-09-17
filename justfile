export PYTHONPATH := justfile_directory() / "backend"

default:
  @just --list

run:
    uv sync --locked
    uv run -m query_service

up:
    docker compose up -d --wait db
    uv run alembic upgrade head
    just run

down:
    docker compose down -v
