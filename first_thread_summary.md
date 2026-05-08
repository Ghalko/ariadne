# First Thread Summary

## Current Handoff - 2026-05-01

Completed checkpoint:

- Branch: `master`
- Commit: `efc05d0` (`long haiatus`)
- Files included:
  - `src/ariadne_index/config.py`
  - `src/ariadne_index/services/indexing.py`
  - `src/ariadne_index/services/repository.py`
  - `tests/test_indexing_and_retrieval.py`
  - `tests/test_mcp_server.py`
  - `first_thread_summary.md`
- Verification:
  - `/Users/ghalko/.local/bin/uv run pytest tests/test_indexing_and_retrieval.py tests/test_mcp_server.py` passed, 14 tests.
  - `/Users/ghalko/.local/bin/uv run pytest` passed, 16 tests.
  - Live MCP reindex passed for `ariadne`, `spinner`, and `quay`.
- Live Postgres status: `ariadne doctor` reports no issues, `vector(1024)`, and stored embeddings at 1024 dimensions.
- Durable memory added: `Ariadne handoff discipline under tighter token budgets` (`id=23`).

Current implementation focus:

- Recursive default excludes now cover nested `.git`, `node_modules`, virtualenvs, build outputs, `__pycache__`, and `.pytest_cache`.
- `IndexingService.index_repo()` refreshes repo git metadata before indexing.
- Indexing now excludes registered nested repos when indexing a parent workspace.
- Reindexing prunes stale file records, stale symbols, stale graph edges, and stale embeddings for files no longer discovered.
- Symbol replacement now cleans up graph edges and embeddings for replaced symbols.
- `RepoService.refresh_repo_metadata()` updates branch and commit metadata; MCP `repo_index` is covered by a test that commit metadata changes after a new git commit.

Likely next action:

- Dogfood the documented Codex MCP flow in normal Ariadne work.
- Run the ContextBench adapter against a small local checkout set.
- Then design the conversation/session ingest path and reviewable memory capture flow.

This file captures the highest-signal outcomes from the first long build thread: what was decided, what was built, and what still exists only as an idea, partial implementation, or undocumented operational knowledge.

## Built

- Core Ariadne scaffold:
  - repo registration
  - indexing
  - Python and TS/JS parsing
  - graph storage
  - memory CRUD
  - CLI
  - FastAPI
  - hybrid retrieval
  - context packing
- Podman-first Postgres setup using an AWS ECR Public Postgres base image
- `uv`-based Python workflow
- deterministic embeddings as the stable default
- optional OpenAI embedding path using `text-embedding-3-small`
- benchmark fixtures:
  - `spinner`
  - `quay`
- benchmark harnesses:
  - temp-DB fixture benchmarks
  - live Postgres-backed fixture benchmarks
- retrieval diagnostics:
  - stage counts
  - ranked candidates
  - persisted retrieval logs
  - CLI/API trace surfaces
- DB compatibility tooling:
  - `ariadne doctor`
  - `ariadne reconcile-embeddings`
  - optional strict DB compatibility enforcement
- first Ariadne MCP server:
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

## Important Decisions

- Ariadne should remain a retrieval, graph, memory, and context-packing system, not an IDE shell.
- Postgres remains the shared/team system of record.
- SQLite should be treated as a first-class single-developer local mode, not only as a test convenience.
- Graph and memory are first-class, not side-effects of vector retrieval.
- Benchmarks should drive retrieval work more than intuition.
- Spinner and Quay together are the right current evaluation set.
- MCP dogfooding in Codex is the next meaningful product-validation step.

## Built But Still Thin

These exist, but are still MVP-grade or operationally incomplete.

- `TEST_COVERS_SYMBOL`
- `DOC_DESCRIBES_SYMBOL`
- `DOC_DESCRIBES_FILE`
- `CONFIG_AFFECTS_FILE`
- memory-to-code linking
- retrieval traces
- MCP surface

Remaining weakness is mostly:

- doc and config ranking
- top-level `README.md` recall
- a few `not_generated` symbols
- ergonomics of agent-side memory capture

## Discussed But Not Yet Built

### 1. Commit nodes

Still not implemented.

Planned shape:

- `commits` table
- `COMMIT_TOUCHED_FILE`
- later `COMMIT_MODIFIED_SYMBOL`
- commit-aware memory and history retrieval

### 2. Human-in-the-loop linking

Still not implemented.

Planned use:

- docs to files/symbols
- ADRs to subsystems
- incidents to code paths
- cross-tree and cross-repo reviewed links

### 3. Conversation/session ingest

Still not implemented.

This became more important after looking at MemPalace.

Needed:

- ingest chat/session exports
- preserve raw transcripts
- derive candidate memories
- require review before durable persistence where confidence is weak

### 4. Pre-compaction capture hooks

Still not implemented.

Desired behavior:

- capture useful transient session context before it is summarized away
- fit Codex/Claude-style coding-agent workflows

### 5. MCP dogfooding configuration

Status: implemented in MVP form in `docs/codex-mcp-dogfooding.md` and `scripts/mcp_smoke.py`.

Still useful follow-ups:

- keep the guide current as Codex MCP config changes
- add smoke coverage for cross-repo retrieval if `spinner` and `quay` become first-class dogfooding targets
- turn repeated retrieval misses found through dogfooding into benchmark cases

### 6. Public benchmark integration

Status: first adapter implemented for ContextBench in `benchmarks/run_contextbench.py`.

Current public benchmark targets:

- ContextBench
- RepoBench
- CrossCodeEval
- SWE-bench variants

ContextBench is first because it directly scores coding-agent context retrieval quality and efficiency. The adapter expects exported ContextBench rows plus local checked-out repos at the benchmark `base_commit`, then reports file recall, file precision, optional snippet span recall, packed token estimate, gold-context token estimate, and recall per 1k packed tokens.

Still needed:

- add baselines and diagnostics to the ContextBench runner
- compare against simple lexical/raw-file baselines
- improve query rewriting for long issue statements

First real smoke result:

- exported 2 verified ContextBench rows
- cloned `astropy/astropy`
- evaluated one instance at base commit `6500928dc0e57be8f06d1162eacc3ba5e2eff692`
- first result: file recall `0.0`, file precision `0.0`, packed token estimate `922`, gold-context token estimate `3572`
- diagnostic rerun with baselines: Ariadne recall `0.0`, simple baseline recall `0.1111`, Ariadne packed token estimate `984`, baseline token estimate `250`
- missing-file reasons: `not_generated=9`, `scored_too_low=0`, `packed_out=0`
- interpretation: Ariadne was compact but missed all gold files, so token reduction is not meaningful yet on this public case
- avoid overfitting this one Astropy row; run 5-10 diagnostic rows before changing ranking behavior

### 7. Compression experiments

Still not implemented.

TurboQuant was noted as a future semantic-layer optimization idea, but no compressed-vector benchmark track exists yet.

### 8. Multi-user/team deployment story

Only partially documented.

We agreed on:

- SQLite for single-dev local mode
- Postgres for shared/team mode

But there is no explicit deployment guide yet for:

- small team self-hosted setup
- managed/cloud Postgres setup
- auth/access-control model

## Built During The Thread But Easy To Forget

- The live Postgres DB was reconciled from `vector(24)` to `vector(1024)`.
- Retrieval-log diagnostics are now persisted.
- `ariadne doctor` is the first-line DB compatibility check.
- `ariadne reconcile-embeddings` is the intended recovery path for embedding-dimension drift.
- The MCP server is stdio-based and intended for Codex dogfooding.

## Current Retrieval Gaps Worth Chasing Next

These were still showing up after the reconciliation and live validation work:

- Spinner:
  - `build_plan`
  - `load_openai_settings`
  - `record_session_run`
  - `semantic_candidates`
  - `README.md`
- Quay:
  - `append_audit_event`
  - `config/auth.toml`
  - `README.md`

These are better next targets than broad ranking changes.

## Recommended Next Order

1. Dogfood Ariadne via MCP in Codex.
2. Document the Codex MCP setup and preferred Ariadne tool flows.
3. Add conversation/session ingest with reviewable candidate memories.
4. Close the remaining concrete symbol and support-artifact retrieval gaps.
5. Add commit nodes and human-in-the-loop linking.
6. Add public benchmark adapters only after the Codex dogfooding loop is productive.

## References From The Thread

- MemPalace: <https://github.com/milla-jovovich/mempalace>
- TurboQuant blog: <https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/>
