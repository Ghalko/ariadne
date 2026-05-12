# SQLite Branch Workflow

Ariadne can distribute curated SQLite seed DBs, but git cannot merge active SQLite files. Treat SQLite files as binary snapshots and use Ariadne commands to create and merge branch DBs.

## Branch DBs

Each working branch gets its own copy:

```bash
ariadne sqlite init-branch
ariadne sqlite branch-path
```

On branch `sqlite`, the default path is:

```text
seed/branches/sqlite.sqlite
```

Point Codex MCP at that branch DB while working:

```toml
[mcp_servers.ariadne.env]
ARIADNE_DATABASE_URL = "sqlite+pysqlite:////Users/ghalko/ariadne_index/seed/branches/sqlite.sqlite"
ARIADNE_EMBEDDING_PROVIDER = "deterministic"
ARIADNE_STRICT_DB_COMPATIBILITY = "true"
```

Restart Codex after changing MCP config.

## Merge Model

Do not resolve branch DB changes by accepting one binary file over another.

Use an Ariadne-level merge:

```bash
ariadne sqlite merge seed/branches/feature-x.sqlite seed/ariadne.sqlite
ariadne sqlite merge seed/branches/feature-x.sqlite seed/ariadne.sqlite --apply
```

The merge is dry-run by default. It maps rows by UUID when present, then falls back to stable or natural keys:

- repos by name
- files by repo and path
- symbols by file, name, and line range
- memories by repo, title, content, summary, type, and source
- edges by remapped endpoints, edge type, and metadata
- embeddings by remapped node and embedding role

Retrieval logs are high-churn and are skipped by default. Include them only when preserving evidence is intentional:

```bash
ariadne sqlite merge seed/branches/feature-x.sqlite seed/ariadne.sqlite --include-retrieval-logs --apply
```

## Preflight

Before committing any seed or branch DB:

```bash
ariadne compact --database-url sqlite+pysqlite:///seed/branches/sqlite.sqlite --apply --keep-retrieval-logs 100
ariadne doctor --database-url sqlite+pysqlite:///seed/branches/sqlite.sqlite
ariadne scan-db-secrets --database-url sqlite+pysqlite:///seed/branches/sqlite.sqlite
```

Only commit if `doctor` has no issues and `scan-db-secrets` reports `ok_to_distribute: true`.

## Limits

This is a bridge until UUID-backed memory export/import exists.

The current merge has UUID row identity for repos, files, symbols, memories, edges, embeddings, and retrieval logs. It still works best when branch DBs descend from the same seed. It is not a general relational database merge engine, and it should be treated as moderated infrastructure for Ariadne's schema only.
