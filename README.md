# Ariadne

A local-first repository index for AI coding workflows backed by Postgres, `pgvector`, and an explicit graph model.

## MVP Scope

- Register and index one or more repositories
- Extract files and symbols for Python and TS/JS
- Store summaries, embeddings, memories, and edges in Postgres
- Combine lexical, graph, semantic, and memory retrieval
- Pack compact context payloads for LLM tasks
- Expose both CLI and FastAPI surfaces

## Layout

- `src/ariadne_index/`: application package
- `alembic/`: migration environment
- `examples/`: example packed-context output
- `tests/`: indexing and retrieval tests

## Quick Start

```bash
uv python install 3.14
uv sync --python 3.14 --extra dev --extra postgres --extra treesitter
uv run --python 3.14 alembic upgrade head
uv run --python 3.14 ariadne add-repo /path/to/repo --name repo-name
uv run --python 3.14 ariadne index repo-name
uv run --python 3.14 ariadne retrieve "refactor retry logic" --mode refactor
uv run --python 3.14 uvicorn ariadne_index.api:app --reload
```

## Podman Postgres

This repo includes a Podman-first container setup for local Postgres with `pgvector`.
The database image is built locally from the AWS ECR Public Postgres base image
`public.ecr.aws/docker/library/postgres:17-bookworm`, then `pgvector` is installed during the build.

```bash
cp .env.example .env
set -a
source .env
set +a

podman compose build postgres
podman compose up -d postgres
podman compose ps

uv python install 3.14
uv sync --python 3.14 --extra dev --extra postgres --extra treesitter

uv run --python 3.14 alembic upgrade head
uv run --python 3.14 ariadne add-repo /path/to/repo --name repo-name
uv run --python 3.14 ariadne index repo-name
uv run --python 3.14 ariadne retrieve "refactor retry logic" --mode refactor --repo-name repo-name
```

Useful Podman commands:

```bash
podman compose down
podman compose down -v
podman compose logs -f postgres
podman exec -it ariadne-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Useful `uv` commands:

```bash
uv sync --python 3.14 --extra dev --extra postgres --extra treesitter
uv run --python 3.14 pytest -q
uv run --python 3.14 ariadne repos
uv run --python 3.14 ariadne pack-context "refactor retry logic" --mode refactor --repo-name repo-name
uv run --python 3.14 uvicorn ariadne_index.api:app --reload
```

Verify `pgvector` is enabled:

```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

## Notes

- Postgres is the intended system of record for production use.
- Tests use SQLite with a fallback embedding column implementation.
- Tree-sitter integration is optional at runtime and falls back to heuristic extraction where unavailable.
- `compose.yaml` uses the standard Compose format but is intended to be run with `podman compose`.
- The Postgres base image is AWS-hosted; `pgvector` is compiled into that image at build time.
- Use `uv python install 3.14` and `uv run --python 3.14 ...` instead of relying on a system-managed Python.
