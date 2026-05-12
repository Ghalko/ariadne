# Ariadne

A local-first repository index for AI coding workflows backed by Postgres, `pgvector`, and an explicit graph model.

## Research Motivation

Coding agents often spend substantial context budget rediscovering repository structure: searching for files, reading nearby tests, finding docs and config, and recovering prior decisions. Ariadne treats context retrieval as an explicit planning and indexing problem rather than a series of ad hoc file reads.

The goal is to measure whether graph-backed retrieval, embeddings, durable memory, and compact context packing can reduce redundant tool calls and token usage while preserving or improving task success.

Current evidence and known failures are summarized in [docs/evidence-report.md](docs/evidence-report.md). The short version: internal fixture retrieval is functional, MCP dogfooding works, and the first public ContextBench smoke showed Ariadne was compact but missed the gold context. That failure is now part of the benchmark record rather than hidden.

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

## Install Podman

For macOS, install Podman before starting Postgres.

Recommended:

- Download the official macOS installer from Podman: <https://podman.io/docs/installation>

Homebrew alternative:

```bash
brew install podman
```

Install a Compose provider too:

```bash
brew install podman-compose
```

After installing Podman on macOS, initialize and start the Podman machine:

```bash
podman machine init
podman machine start
podman info
podman compose version
```

## Quick Start

```bash
uv python install 3.14
uv venv --python 3.14
source .venv/bin/activate
uv sync --extra dev --extra postgres --extra treesitter
alembic upgrade head
ariadne add-repo /path/to/repo --name repo-name
ariadne index repo-name
ariadne retrieve "refactor retry logic" --mode refactor
uvicorn ariadne_index.api:app --reload
```

## Podman Postgres

This repo includes a Podman-first container setup for local Postgres with `pgvector`.
The database image is built locally from the AWS ECR Public Postgres base image
`public.ecr.aws/docker/library/postgres:17-bookworm`, then `pgvector` is installed during the build.

Development connection defaults:

- Database: `ariadne`
- User: `ariadne`
- Password: `ariadne`
- Host: `127.0.0.1`
- Port: `5432`

Embedding defaults:

- Provider: `openai` when `OPENAI_API_KEY` is set, otherwise deterministic local fallback
- Model: `text-embedding-3-small`
- Dimensions: `1024`

```bash
cp .env.example .env
set -a
source .env
set +a

podman compose build postgres
podman compose up -d postgres
podman compose ps

uv python install 3.14
uv venv --python 3.14
source .venv/bin/activate
uv sync --extra dev --extra postgres --extra treesitter

alembic upgrade head
ariadne add-repo /path/to/repo --name repo-name
ariadne index repo-name
ariadne retrieve "refactor retry logic" --mode refactor --repo-name repo-name
```

Useful Podman commands:

```bash
podman compose down
podman compose down -v
podman compose logs -f postgres
podman exec -it ariadne-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

If `podman compose` still does not find a provider, run the provider directly:

```bash
podman-compose build postgres
podman-compose up -d postgres
podman-compose ps
```

Useful `uv` commands:

```bash
uv sync --extra dev --extra postgres --extra treesitter
pytest -q
ariadne repos
ariadne doctor
ariadne reconcile-embeddings
ariadne trace "What config and docs describe provider selection and fallback?" --mode docs --repo-name repo-name
ariadne retrieval-logs --repo-name repo-name --limit 5
ariadne pack-context "refactor retry logic" --mode refactor --repo-name repo-name
uvicorn ariadne_index.api:app --reload
```

Move existing Ariadne Postgres data into a local SQLite file:

```bash
mkdir -p .ariadne
ariadne migrate-postgres-to-sqlite .ariadne/ariadne.db \
  --source-database-url postgresql+psycopg://ariadne:ariadne@127.0.0.1:5432/ariadne
ARIADNE_DATABASE_URL=sqlite+pysqlite:///.ariadne/ariadne.db ariadne doctor
```

Control local DB growth:

```bash
ariadne compact
ariadne compact --apply --keep-retrieval-logs 100
ariadne compact --apply --reindex --keep-retrieval-logs 100
ariadne backfill-uuids
```

Before distributing or committing a curated SQLite seed DB, run:

```bash
ARIADNE_DATABASE_URL=sqlite+pysqlite:///.ariadne/ariadne.db ariadne doctor
ARIADNE_DATABASE_URL=sqlite+pysqlite:///.ariadne/ariadne.db ariadne scan-db-secrets
```

For branch-specific SQLite DBs and moderated DB merges, see [docs/sqlite-branch-workflow.md](docs/sqlite-branch-workflow.md).

## MCP

Ariadne can run as a local stdio MCP server for agent integrations.

Available MCP tools include:

- `repo_list`
- `repo_add`
- `repo_index`
- `search`
- `retrieve`
- `pack_context`
- `trace`
- `graph`
- `memory_list`
- `memory_add`
- `memory_link`
- `retrieval_logs`
- `doctor`

Run it locally:

```bash
ariadne-mcp
```

Or with `uv`:

```bash
uv run ariadne-mcp
```

For Codex dogfooding, use the setup and workflow in [docs/codex-mcp-dogfooding.md](docs/codex-mcp-dogfooding.md).

After changing MCP config or restarting Postgres, run the smoke check:

```bash
uv run python scripts/mcp_smoke.py --repo ariadne
```

If you do not want to activate the virtualenv, use `uv run` instead:

```bash
uv run --python 3.14 ariadne --help
uv run --python 3.14 pytest -q
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
- `podman compose` requires an external compose provider such as `podman-compose`; it is not a built-in compose engine.
- The Postgres base image is AWS-hosted; `pgvector` is compiled into that image at build time.
- Use `uv python install 3.14`, `uv venv --python 3.14`, and `source .venv/bin/activate` for the normal interactive workflow.
- If you created an older local database with 24-dimensional embeddings, recreate it before switching to the new 1024-dimensional OpenAI setup.
- `ariadne doctor` checks schema state, `pgvector`, and embedding-dimension compatibility.
- `ariadne reconcile-embeddings` rebuilds the embeddings layer in place and is the intended recovery path when the vector dimensions drift from the configured default.
- `ariadne migrate-postgres-to-sqlite` copies Ariadne application tables into a local SQLite file, preserving integer IDs so graph edges and embeddings remain connected.
- `ariadne compact` prunes old retrieval logs and orphaned graph/vector rows, then runs SQLite `VACUUM` when applied.
- `ariadne scan-db-secrets` fails if the DB has secret-shaped paths or unredacted secret-looking values.
- `ariadne backfill-uuids` adds and populates UUID identity columns used by branch DB merges.
- If your local DB is still on the older `vector(24)` schema, either recreate it at `1024` or temporarily run with `ARIADNE_EMBEDDING_DIMENSIONS=24`.
- Set `ARIADNE_STRICT_DB_COMPATIBILITY=true` if you want Ariadne to fail fast when the configured embedding dimensions do not match the live DB.
- `ariadne-mcp` speaks stdio MCP and is intended to be the dogfooding path for Codex and other MCP-capable agents.
