# Spinner

## Purpose

`spinner` is the first internal fixture repo for Ariadne.

It should be:

- realistic enough to exercise retrieval, graph expansion, memory linking, and context packing
- small enough to understand and evolve quickly
- structured enough to support hand-labeled benchmark tasks

`spinner` is not a full IDE.

It is a local AI coding runtime and orchestration backend that a future IDE could sit on top of.

That makes it a much better evaluation target for Ariadne because it naturally contains:

- repo indexing logic
- retrieval logic
- context packing
- agent/task execution
- provider abstractions
- patch application
- sessions and history
- operational docs and architecture notes

## What Spinner Does

At a high level, `spinner` should:

- index local repositories
- retrieve relevant code and docs for coding tasks
- assemble compact context for an agent
- run tool-backed coding tasks against a workspace
- generate and apply patches
- track sessions, runs, and failures
- store operational and architectural notes

This gives us a repo with real cross-file relationships without needing to build a whole editor UI.

## Main Product Story

The user interacts with `spinner` through a CLI or lightweight local API.

A typical flow:

1. Register a workspace.
2. Index the repo.
3. Ask a coding question or task.
4. Retrieve relevant code, docs, and memories.
5. Build a compact agent context.
6. Execute tools or propose a patch.
7. Record session history, outcomes, and notes.

That gives us code paths that naturally create benchmarkable retrieval tasks.

## Subsystems

### 1. Workspace

Responsibilities:

- register local repos
- track active branch and commit
- maintain include/exclude rules
- expose workspace metadata

Possible files:

- `spinner/workspace/registry.py`
- `spinner/workspace/status.py`
- `spinner/workspace/discovery.py`

### 2. Indexing

Responsibilities:

- discover files
- parse symbols
- generate summaries
- build graph edges
- persist indexing state

Possible files:

- `spinner/indexing/indexer.py`
- `spinner/indexing/parsers/python_parser.py`
- `spinner/indexing/parsers/ts_parser.py`
- `spinner/indexing/graph_builder.py`
- `spinner/indexing/summaries.py`

### 3. Retrieval

Responsibilities:

- lexical search
- semantic retrieval
- graph expansion
- memory retrieval
- candidate ranking

Possible files:

- `spinner/retrieval/lexical.py`
- `spinner/retrieval/semantic.py`
- `spinner/retrieval/graph.py`
- `spinner/retrieval/ranking.py`
- `spinner/retrieval/pipeline.py`

### 4. Context Packing

Responsibilities:

- summarize relevant artifacts
- choose snippets
- estimate token usage
- deduplicate overlapping context
- tailor output by task mode

Possible files:

- `spinner/context/packer.py`
- `spinner/context/token_budget.py`
- `spinner/context/snippets.py`
- `spinner/context/modes.py`

### 5. Agent Runtime

Responsibilities:

- accept tasks
- prepare prompts
- choose tools
- track execution status
- handle retries and failure states

Possible files:

- `spinner/agent/runtime.py`
- `spinner/agent/tasks.py`
- `spinner/agent/planner.py`
- `spinner/agent/executor.py`

### 6. Patching

Responsibilities:

- generate patches
- validate patch safety
- apply patches
- roll back failed patch attempts

Possible files:

- `spinner/patching/diff.py`
- `spinner/patching/apply.py`
- `spinner/patching/rollback.py`
- `spinner/patching/validation.py`

### 7. Providers

Responsibilities:

- model provider abstractions
- embedding provider abstractions
- fallback behavior
- provider configuration

Possible files:

- `spinner/providers/chat.py`
- `spinner/providers/embeddings.py`
- `spinner/providers/openai.py`
- `spinner/providers/deterministic.py`

### 8. Sessions and History

Responsibilities:

- store session state
- record prompts, retrievals, and outcomes
- expose prior runs
- support replay or audit

Possible files:

- `spinner/sessions/store.py`
- `spinner/sessions/history.py`
- `spinner/sessions/replay.py`

### 9. Telemetry and Incidents

Responsibilities:

- log retrieval and execution events
- surface failures
- track notable incidents
- support runbooks

Possible files:

- `spinner/telemetry/events.py`
- `spinner/telemetry/logging.py`
- `spinner/telemetry/incidents.py`

### 10. API and CLI

Responsibilities:

- provide local command surface
- expose local API endpoints
- render human-readable output

Possible files:

- `spinner/api/app.py`
- `spinner/api/routes/retrieve.py`
- `spinner/api/routes/tasks.py`
- `spinner/cli.py`

## Suggested Repo Shape

```text
spinner/
  pyproject.toml
  README.md
  spinner/
    api/
    agent/
    context/
    indexing/
    patching/
    providers/
    retrieval/
    sessions/
    telemetry/
    workspace/
  tests/
    unit/
    integration/
    fixtures/
  docs/
    adr/
    runbooks/
    architecture/
  config/
    spinner.toml
    providers.toml
    retrieval.toml
```

## What Makes Spinner Useful for Ariadne

`spinner` should deliberately contain relationships that are not all obvious from one file.

Examples:

- retrieval pipeline calls context packing, which depends on token budgeting
- agent execution depends on retrieval mode and provider configuration
- patch application rollback depends on session state and validation
- incidents reference patching failures and retrieval overload
- ADRs constrain provider selection and tool sandboxing

This gives Ariadne meaningful graph traversal problems.

## Documents to Include

### ADRs

At least 4-6 architecture docs.

Examples:

- `docs/adr/001-summary-first-context.md`
- `docs/adr/002-tool-sandboxing.md`
- `docs/adr/003-provider-fallback-strategy.md`
- `docs/adr/004-patch-rollback-policy.md`
- `docs/adr/005-retrieval-stage-order.md`

### Runbooks

At least 3-4 operational notes.

Examples:

- `docs/runbooks/retrieval-latency-spike.md`
- `docs/runbooks/patch-apply-failures.md`
- `docs/runbooks/provider-rate-limit-response.md`

### Architecture Notes

Examples:

- `docs/architecture/retrieval-flow.md`
- `docs/architecture/session-lifecycle.md`
- `docs/architecture/provider-abstractions.md`

## Memories We Should Be Able to Derive Later

These can start as docs and later become explicit memory nodes in Ariadne.

Examples:

- summary-first context is preferred to raw-file dumping
- patch application must be reversible
- provider fallback should prefer deterministic/local behavior when upstream quota fails
- retrieval should keep test and config expansion bounded
- sandboxing constraints apply to file writes and command execution

## Benchmark Tasks Spinner Should Support

### Retrieval Tasks

- "Find where context packing excludes large files."
- "Find the retrieval stage ordering logic."
- "Which files govern provider fallback?"
- "What code handles patch rollback?"
- "Where is session replay implemented?"

### Refactor Tasks

- "Refactor token budgeting and surface decisions that matter."
- "Change provider fallback behavior and expand to affected tests and docs."
- "Update patch validation and find all related rollback paths."

### Historical / Memory Tasks

- "What prior decision applies to tool sandboxing?"
- "What runbook note relates to patch apply failures?"
- "Which architecture note explains retrieval stage order?"

### Test Expansion Tasks

- "Find tests covering patch rollback."
- "Which tests exercise provider fallback?"
- "Expand from retrieval ranking to its integration tests."

## Complexity Target

The repo should be big enough to be useful, but not so big that it becomes expensive to maintain.

Suggested initial target:

- 25-40 source files
- 15-25 tests
- 8-12 docs across ADRs, runbooks, and architecture notes
- 3-5 config files
- multiple subsystems with overlapping terminology

## Design Rules for Spinner

- keep the repo realistic, not toy-like
- avoid perfect cleanliness; include a few mildly confusing cross-file relationships
- include both obvious and non-obvious retrieval paths
- make docs operationally meaningful, not filler
- include at least one incident-prone area: patch apply failure or provider fallback
- include at least one config-heavy area: retrieval mode or provider policy

## Suggested Build Order

1. Create repo structure and `pyproject.toml`.
2. Add core packages: workspace, retrieval, context, agent, patching.
3. Add tests that cross subsystem boundaries.
4. Add ADRs, runbooks, and architecture docs.
5. Add a few intentionally overlapping concepts: fallback, rollback, sandbox, token budget.
6. Label benchmark tasks against the repo.
7. Add it as a submodule or nested fixture repo for Ariadne benchmarking.

## Why This Is Better Than a Full IDE Fixture

A full IDE fixture would immediately drag in:

- editor state
- panes and layout
- keyboard handling
- UI rendering
- extension lifecycle

That is mostly noise for Ariadne’s current evaluation goals.

`spinner` as a local coding runtime keeps the fixture focused on the retrieval and memory problems we actually need to solve first.
