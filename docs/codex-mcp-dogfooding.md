# Codex MCP Dogfooding

This document is the working setup and operating loop for using Ariadne from Codex through MCP.

## Preconditions

- Postgres is running and reachable at the configured `ARIADNE_DATABASE_URL`.
- The database has been initialized and migrated.
- `ariadne doctor` reports no issues.
- The repo has a local virtualenv with Ariadne installed, or Codex can run Ariadne through `uv`.

For this checkout, the known-good live state is:

- database URL: `postgresql+psycopg://ariadne:ariadne@127.0.0.1:5432/ariadne`
- embedding provider: `deterministic`
- embedding dimensions: `1024`
- strict DB compatibility: enabled
- registered repos: `ariadne`, `spinner`, `quay`

## Codex Config

The local Codex config uses this shape:

```toml
[mcp_servers.ariadne]
command = "/Users/ghalko/ariadne_index/.venv/bin/ariadne-mcp"
cwd = "/Users/ghalko/ariadne_index"
enabled = true

[mcp_servers.ariadne.env]
ARIADNE_DATABASE_URL = "postgresql+psycopg://ariadne:ariadne@127.0.0.1:5432/ariadne"
ARIADNE_EMBEDDING_PROVIDER = "deterministic"
ARIADNE_STRICT_DB_COMPATIBILITY = "true"
```

If the virtualenv entry point is not available, use `uv` instead:

```toml
[mcp_servers.ariadne]
command = "/Users/ghalko/.local/bin/uv"
args = ["run", "ariadne-mcp"]
cwd = "/Users/ghalko/ariadne_index"
enabled = true

[mcp_servers.ariadne.env]
ARIADNE_DATABASE_URL = "postgresql+psycopg://ariadne:ariadne@127.0.0.1:5432/ariadne"
ARIADNE_EMBEDDING_PROVIDER = "deterministic"
ARIADNE_STRICT_DB_COMPATIBILITY = "true"
```

Restart Codex after changing MCP config so the tool list is refreshed.

## Smoke Check

After starting Postgres or changing MCP config, run:

```bash
/Users/ghalko/.local/bin/uv run python scripts/mcp_smoke.py --repo ariadne
```

The smoke check:

- initializes the MCP server in-process
- lists MCP tools
- runs `doctor`
- runs `repo_index`
- checks that `repo_list` reports the current git commit for the repo
- runs a small `pack_context` query

Use this to localize failures before debugging Codex integration. If this fails, the problem is in Ariadne, the DB, or local environment configuration.

## Tool Flow

Start every dogfooding thread with read-only inspection:

```text
doctor
repo_list
memory_list(repo_name="ariadne")
```

For code work, prefer this order:

1. `pack_context` for the main task prompt.
2. `search` when you need fast lexical narrowing by exact file, symbol, or phrase.
3. `trace` when the packed context looks wrong or noisy.
4. `graph` when you have a concrete file, symbol, or memory id and need nearby edges.
5. `retrieval_logs` after a session to inspect what Ariadne selected and packed.

Use `retrieve` when you need scores and full diagnostics in one payload. Use `pack_context` when you only need the compact task context.

## Modes

Use modes intentionally:

- `understand`: code reading, architecture questions, locating behavior.
- `bugfix`: defects, regressions, failing tests, suspicious behavior.
- `refactor`: changing structure while preserving behavior.
- `testgen`: finding production code plus relevant tests.
- `docs`: documentation, runbooks, ADRs, config, and support artifacts.
- `architecture`: high-level decisions, subsystem relationships, durable context.

Keep `include_code=false` for planning and broad inspection. Use `include_code=true` only when the agent needs snippets directly in the packed payload.

## Memory Discipline

Use Ariadne memory for durable engineering facts, not verbose chat logs.

Good memory candidates:

- decisions that should survive compaction
- project direction and constraints
- recurring operational lessons
- reviewed links between a decision and a file, symbol, doc, or config

Avoid storing:

- one-off command output
- temporary guesses
- full session transcripts
- facts that are already obvious from committed code

When adding memory:

1. Make the title specific.
2. Keep the summary short.
3. Put evidence and context in the content.
4. Link it with `memory_link` only when the target node is known and the relationship is durable.

## Query Patterns

Good:

```text
repo_name="ariadne"
mode="bugfix"
query="review indexing changes for nested repos pruning stale files embeddings and repo metadata refresh"
```

```text
repo_name="ariadne"
mode="docs"
query="document Codex MCP setup and dogfooding workflow for Ariadne tools"
```

```text
repo_name="spinner"
mode="understand"
query="where is token budgeting and context packing implemented"
```

Weak:

```text
query="fix this"
```

```text
query="what happened yesterday"
```

```text
query="everything about retrieval"
```

Make the query name the repo area, behavior, and expected artifact type when possible.

## Troubleshooting

If tools are missing in Codex:

- confirm the MCP config has `enabled = true`
- restart Codex
- run the smoke check
- verify `ariadne-mcp` exists in the configured virtualenv

If tools return DB errors:

- confirm Postgres is up
- run `ariadne doctor`
- verify `ARIADNE_DATABASE_URL`
- check `ARIADNE_STRICT_DB_COMPATIBILITY`

If retrieval is noisy:

- run `trace` for the same query
- inspect `stage_counts`, `top_ranked`, and `packed`
- try a more concrete mode
- include symbol, file, config, or doc names in the query
- record repeated failure patterns as benchmark or ranking work, not as ad hoc memories

## Current Next Dogfooding Targets

- Use Ariadne at the start of each Ariadne coding thread.
- Capture durable decisions with `memory_add`.
- Link memories only when the target node is clear.
- Use `trace` and `retrieval_logs` to identify retrieval ranking issues.
- Convert repeated retrieval misses into benchmark cases.
