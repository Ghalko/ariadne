# SQLite-First Distributed Development Plan

This branch explores moving Ariadne's default collaboration story toward SQLite sooner, while keeping Postgres as a supported shared/team backend.

## Goals

- Make local setup simple enough for public GitHub collaborators.
- Avoid requiring Postgres for first contribution, docs work, parser work, benchmark work, or MCP dogfooding.
- Reduce migration merge conflicts from linear Alembic revision chains.
- Allow users to inspect pending schema changes before applying them to durable local data.
- Prepare for distributed databases and exported graph/memory snapshots where integer IDs are not stable enough.

## Current State

- `ARIADNE_DATABASE_URL` already defaults to `sqlite+pysqlite:///:memory:`.
- Tests use SQLite successfully.
- Postgres remains the richer backend because it has `pgvector` and HNSW indexing.
- Alembic currently owns migrations through:
  - `0001_initial_schema`
  - `0002_retrieval_diagnostics`
- Most table primary keys are auto-incrementing integers.
- Edges and embeddings point at nodes by `(node_kind, node_id)`, where `node_id` is currently an integer.

## Recommendation

Move in three stages.

### Stage 1: SQLite-first local mode

Keep SQLAlchemy models for runtime ORM behavior, but stop presenting Alembic as the required public setup path.

Add:

- `ariadne doctor` shows migration status
- `ariadne update` applies pending raw SQL migrations
- a default file DB path for local use, probably `.ariadne/ariadne.db`
- docs that say SQLite is the default contributor mode
- Postgres docs moved to "shared/team/advanced mode"

Do not remove Postgres or Alembic immediately. First prove the raw SQL path.

### Stage 2: Raw SQL migrations

Use explicit SQL files and a tracking table instead of Alembic revision scripts.

Directory shape:

```text
migrations/
  0001_base/
    sqlite.sql
    postgres.sql
    metadata.json
  0002_retrieval_diagnostics/
    sqlite.sql
    postgres.sql
    metadata.json
```

Tracking table:

```sql
CREATE TABLE IF NOT EXISTS ariadne_schema_migrations (
  migration_id TEXT PRIMARY KEY,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  description TEXT,
  source TEXT
);
```

Rules:

- migration IDs are stable strings, not Alembic parent pointers
- each migration is idempotent where practical
- the table records checksum so edited applied migrations are detectable
- `ariadne doctor` reports:
  - applied migrations
  - pending migrations
  - checksum mismatches
  - dialect-specific compatibility issues
- `ariadne update` applies pending migrations in lexical order by default
- `ariadne update --dry-run` prints pending migrations and checksums
- `ariadne update --to MIGRATION_ID` applies through a target
- `ariadne update --allow-dirty` or similar can be added later for advanced local recovery, but should not be default

This still has an order, but it removes Alembic's branch-chain conflict model. If two contributors add migrations concurrently, lexical names can conflict only if they choose the same ID. A date/time or UUID prefix can reduce that:

```text
20260511_153000_add_commit_nodes
20260511_154500_add_memory_validity_index
```

For public collaboration, a timestamped migration folder is easier to rebase than Alembic `down_revision` conflicts.

### Stage 3: UUID public IDs

Integer IDs are fine inside one database, but not good for distributed merge/export/import.

Prefer a dual-ID model:

- keep local integer `id` as an internal row key for ORM performance and existing code
- add stable UUID public IDs to graph-addressable tables
- migrate edges and embeddings to use public IDs over time

Candidate columns:

```text
repos.uuid
files.uuid
symbols.uuid
memories.uuid
edges.uuid
embeddings.uuid
retrieval_logs.uuid
```

Node identity should become:

```text
node_kind + node_uuid
```

rather than:

```text
node_kind + integer node_id
```

Why dual IDs instead of replacing integer IDs immediately:

- lower blast radius
- existing relationships and tests keep working
- database-local joins stay simple
- public/export/import identity can improve incrementally

Stable UUID generation:

- repos: random UUID at repo registration
- files: UUIDv5 from `(repo_uuid, path)` is attractive because file identity is deterministic across reindex
- symbols: UUIDv5 from `(file_uuid, qualified_name, line_start, line_end)` initially; later use parser-derived stable symbol identity where available
- memories: random UUID unless imported from a source with a stable ID
- edges: UUIDv5 from `(repo_uuid, from_node_uuid, to_node_uuid, edge_type, metadata fingerprint)` if the edge is deterministic; random UUID for reviewed/manual edges
- embeddings: UUIDv5 from `(node_uuid, embedding_role, model_name, dimensions)`

The deterministic UUID choices help distributed collaborators produce the same IDs for the same indexed artifact. Manual memories and reviewed edges should keep random UUIDs plus provenance.

## Doctor and Update UX

`ariadne doctor` should be read-only.

It should answer:

- what database am I connected to?
- what dialect is this?
- does the migration table exist?
- which migrations are applied?
- which migrations are pending?
- are any applied migration checksums different from disk?
- are required tables/columns present?
- are embedding dimensions compatible?
- is this DB using legacy integer-only node addressing?

`ariadne update` should mutate the DB.

It should:

- initialize the migration tracking table if missing
- show a dry-run plan by default in docs
- apply pending SQL migrations
- refuse checksum mismatches unless explicitly overridden
- produce a clear summary of applied migrations

Suggested commands:

```bash
ariadne doctor
ariadne update --dry-run
ariadne update
ariadne update --to 20260511_153000_add_commit_nodes
```

## Data Safety

For local SQLite, recommend:

```bash
cp .ariadne/ariadne.db .ariadne/ariadne.db.backup-$(date +%Y%m%d-%H%M%S)
ariadne update
```

Later, `ariadne update --backup` can automate this.

Do not design migrations around automatic destructive changes. Prefer additive migrations, backfills, and explicit cleanup commands.

## What Not To Do Yet

- Do not rip out Alembic in one change.
- Do not convert every primary key to UUID in one change.
- Do not make SQLite pretend to have pgvector parity.
- Do not make migration application automatic on every command.
- Do not store large generated DBs in git by default.

## Immediate Implementation Slice

The first practical slice should be:

1. Add a raw SQL migration table and migration discovery service.
2. Port the existing schema to `migrations/0001_base/sqlite.sql` and `postgres.sql`.
3. Port retrieval diagnostics to `migrations/0002_retrieval_diagnostics/sqlite.sql` and `postgres.sql`.
4. Add `ariadne update --dry-run` and `ariadne update`.
5. Extend `ariadne doctor` to report migration status.
6. Update README to make SQLite the public contributor default.

After that lands, add UUID columns as a separate migration and dual-write them during indexing/memory creation.
