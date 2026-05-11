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

### Secrets and Local Data Safety

SQLite makes Ariadne easier to run and easier to copy. That raises the bar for keeping secrets out of the index, embeddings, memories, retrieval logs, and packed context.

Default posture:

- exclude secret-shaped paths during indexing:
  - `.env`, `.env.*`
  - `.aws/**`, `.ssh/**`
  - `secrets.*`, `secret.*`, `credentials.*`
  - private key and certificate container extensions such as `.pem`, `.key`, `.p12`, `.pfx`
- redact secret-shaped values before storing:
  - support-file `content_excerpt`
  - file and symbol summaries/docstrings/signatures
  - embedding input and `content_preview`
  - memory title/content/summary/metadata
  - packed code snippets
- keep `.ariadne/` and local DB files out of git by default
- treat local DB export/import as an explicit user action, never a side effect of `doctor` or `update`

`ariadne doctor` should eventually report:

- whether secret-shaped paths are already indexed
- whether stored excerpts/previews contain likely unredacted secrets
- whether the repo `.gitignore` excludes `.ariadne/`
- whether retrieval logs contain pre-redaction packed context from older versions

`ariadne update` can later include a cleanup migration or maintenance command that prunes newly excluded secret files and rewrites stale excerpts/previews where feasible. It should still avoid deleting local data automatically without a clear plan and backup recommendation.

## Postgres to SQLite Migration

The public SQLite path needs a one-command way to carry an existing Ariadne-only Postgres database into a local SQLite file.

Initial command:

```bash
ariadne migrate-postgres-to-sqlite .ariadne/ariadne.db
```

With an explicit source:

```bash
ariadne migrate-postgres-to-sqlite .ariadne/ariadne.db \
  --source-database-url postgresql+psycopg://ariadne:ariadne@127.0.0.1:5432/ariadne
```

Behavior:

- source defaults to `ARIADNE_DATABASE_URL`
- target must be SQLite
- target file must not already exist unless `--overwrite` is passed
- only Ariadne application tables are copied:
  - `repos`
  - `files`
  - `symbols`
  - `memories`
  - `edges`
  - `embeddings`
  - `retrieval_logs`
- original integer IDs are preserved so existing graph edges, embeddings, memories, and retrieval logs remain coherent
- pgvector values are converted into portable JSON arrays for SQLite
- the command is scoped to Ariadne's schema and is not a general Postgres dump tool

Recommended workflow:

```bash
mkdir -p .ariadne
ariadne migrate-postgres-to-sqlite .ariadne/ariadne.db
ARIADNE_DATABASE_URL=sqlite+pysqlite:///.ariadne/ariadne.db ariadne doctor
ARIADNE_DATABASE_URL=sqlite+pysqlite:///.ariadne/ariadne.db ariadne repos
```

Later, this can grow a `--repo-name` filter, a dry-run row-count preview, and a secret-risk scan before writing the SQLite file.

## Database Size and Consolidation

Distributed SQLite files should not grow without bound or become larger than the repository in normal use.

Growth sources:

- retrieval logs, especially packed contexts and diagnostics
- embeddings for files, symbols, and memories
- stale graph edges or embeddings left behind after schema/tool changes
- repeated local experiments and benchmark traces

Policy:

- repos, files, symbols, graph edges, and file/symbol embeddings are rebuildable from the working tree
- durable memories and reviewed/manual memory edges are the highest-value portable data
- retrieval logs are useful evidence, but they are high-churn and should have retention controls
- compaction should be explicit and dry-run by default

Initial command:

```bash
ariadne compact
ariadne compact --apply --keep-retrieval-logs 100
ariadne compact --apply --reindex --keep-retrieval-logs 100
```

Behavior:

- dry-run by default
- keeps the newest retrieval logs and prunes older logs only with `--apply`
- prunes orphaned edges and embeddings
- optionally reindexes repos before pruning
- runs SQLite `VACUUM` after applying changes
- does not delete repos, files, symbols, or memories as a standalone cleanup step

Longer term, distributed memory should move through a mergeable export/import format. SQLite seed DBs can remain convenient runtime artifacts, but shared durable memory should not depend on merging binary DB files in git.

## What Not To Do Yet

- Do not rip out Alembic in one change.
- Do not convert every primary key to UUID in one change.
- Do not make SQLite pretend to have pgvector parity.
- Do not make migration application automatic on every command.
- Do not store large generated DBs in git by default.
- Do not assume redaction is perfect; make secret scanning observable and conservative.

## Immediate Implementation Slice

The first practical slice should be:

1. Add a raw SQL migration table and migration discovery service.
2. Port the existing schema to `migrations/0001_base/sqlite.sql` and `postgres.sql`.
3. Port retrieval diagnostics to `migrations/0002_retrieval_diagnostics/sqlite.sql` and `postgres.sql`.
4. Add `ariadne update --dry-run` and `ariadne update`.
5. Extend `ariadne doctor` to report migration status.
6. Extend `ariadne doctor` with secret-risk checks for indexed paths, excerpts, previews, logs, and `.gitignore`.
7. Keep `ariadne migrate-postgres-to-sqlite` working as the bridge for existing dogfooding data.
8. Keep `ariadne compact` working as the size-control path for distributed SQLite files.
9. Update README to make SQLite the public contributor default.

After that lands, add UUID columns as a separate migration and dual-write them during indexing/memory creation.
