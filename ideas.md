# Ideas

## Current State

The project is past the initial scaffold stage. Ariadne now has:

- repo registration, indexing, parsing, graph storage, memory CRUD, CLI, API, and benchmark harnesses
- a local benchmark fixture repo in `spinner/`
- a second benchmark fixture repo in `quay/`
- a repeatable benchmark runner with miss diagnostics
- live retrieval traces and persisted retrieval-log diagnostics
- a DB doctor path for schema and embedding compatibility checks
- optional strict DB compatibility enforcement at service bootstrap

Current benchmark baselines:

Spinner:

- file hit rate: `1.0`
- symbol hit rate: `1.0`
- test hit rate: `1.0`
- doc hit rate: `0.636`
- memory hit rate: `1.0`
- avg artifact recall: `0.72`

Quay:

- file hit rate: `1.0`
- symbol hit rate: `1.0`
- test hit rate: `0.8`
- doc hit rate: `0.833`
- memory hit rate: `1.0`
- avg artifact recall: `0.692`

Current live benchmark baselines on the existing Postgres DB with `ARIADNE_EMBEDDING_DIMENSIONS=24`:

Spinner live:

- file hit rate: `1.0`
- symbol hit rate: `1.0`
- test hit rate: `1.0`
- doc hit rate: `0.545`
- memory hit rate: `1.0`
- avg artifact recall: `0.705`

Quay live:

- file hit rate: `1.0`
- symbol hit rate: `1.0`
- test hit rate: `0.8`
- doc hit rate: `0.833`
- memory hit rate: `1.0`
- avg artifact recall: `0.717`

Most remaining misses are now:

- `scored_too_low` for docs, support files, and some symbols
- a smaller number of `not_generated` symbols
- almost no `not_generated` files or memories

That means the current bottleneck has shifted from broad candidate generation to ranking, support-artifact preservation, and targeted symbol generation.

## Direction Check

The recent Claude Code source leak is a useful reminder that the value in systems like this is not hidden orchestration tricks.

The durable value should come from:

- retrieval quality
- memory quality
- graph correctness
- permissioning and trust
- benchmark discipline
- packaging and operational rigor

That reinforces the current Ariadne direction:

- keep Ariadne focused on retrieval, graph, memory, and context packing
- avoid prematurely turning it into an IDE shell
- assume implementation details may become visible and build the moat in quality, evals, and operator trust

## Claude Code Takeaways

What we should learn from the leak:

- the moat is not secret prompt glue
- agent products are systems, not just models
- permissioning and inspectability matter
- release and packaging hygiene matter
- evals and reliability matter more than novelty

How that applies here:

- keep building explicit retrieval provenance
- keep memory reviewable and inspectable
- treat packaging and migrations as first-class engineering work
- benchmark on multiple repo shapes, not just one fixture
- prefer transparent system behavior over magic

## TurboQuant Takeaways

Google's TurboQuant work is relevant to Ariadne, but mainly as a future optimization to the semantic retrieval layer, not as a reason to change the architecture.

What it suggests:

- compression advances will make vector retrieval cheaper and more online-friendly
- this is especially relevant for local-first and incremental systems like Ariadne
- semantic retrieval should stay pluggable so we can swap storage/index formats later

What it does not change:

- lexical retrieval is still necessary
- graph traversal is still necessary
- memory and provenance still matter
- a shared team deployment still wants a stronger multi-user system of record than a single local SQLite file

Practical implication for Ariadne:

- keep embeddings/indexing behind a storage abstraction
- separate canonical embeddings from serving/index representations
- plan to benchmark float32 vs compressed retrieval later
- do not block current ranking, graph, and memory work on speculative compression work

## MemPalace Takeaways

Reference:

- [MemPalace repo](https://github.com/milla-jovovich/mempalace)

MemPalace is useful to study, but mostly as a source of product and ingestion ideas rather than as a storage architecture to copy.

What looks worth learning from:

- raw conversation-memory retention instead of aggressively summarizing too early
- MCP-facing memory tools that an agent can call directly
- save and pre-compact hooks that capture useful context before it disappears
- temporal memory and contradiction-checking ideas
- role- or specialist-specific memory views for architect, reviewer, and ops workflows

What we should not copy directly:

- ChromaDB as the primary storage model
- SQLite as the only storage mode
- AAAK as a default compression layer
- README-level benchmark claims without replication in Ariadne's own harness

What this means for Ariadne:

- Ariadne should grow a conversation-ingest layer for chat/session exports
- Ariadne should expose memory and retrieval traces over MCP
- Ariadne should support pre-compaction capture hooks for coding-agent sessions
- Ariadne should support SQLite as an explicit single-developer local mode
- Ariadne should support Postgres as the shared system of record for team use
- Ariadne should treat external memory formats as import sources, not as the core storage contract

## Agentic Memory Research Sweep

Reference:

- [agentic-memory repo](https://github.com/lhl/agentic-memory)

The `agentic-memory` repository looks useful as a curated research and system-review corpus, not as a single architecture to adopt wholesale.

What looks worth reviewing:

- concrete agent memory systems with explicit write/read pipelines and operational tradeoffs
- benchmark and dataset coverage for long-horizon, multi-session, and structured-memory evaluation
- memory evolution, decay, temporal validity, and contradiction-handling approaches
- trust and safety topics such as memory poisoning, weak-memory review, and provenance

What this should drive in Ariadne:

- a structured review pass across the repo's system analyses, not just one-off reading
- a checklist of import, review, retrieval, decay, and benchmarking ideas worth stealing or rejecting explicitly
- replication of useful benchmark ideas in Ariadne's own harness instead of relying on README claims
- comparison of Ariadne's conversation and thread-ingest design against the stronger external memory-system references in that collection

## Storage Modes

Ariadne should treat storage as a deployment mode decision, not as ideology.

### SQLite mode

Best fit:

- single-developer local use
- local-first laptop workflows
- benchmark fixtures and disposable sandboxes
- MCP-sidecar or agent-local memory where one process or one user dominates writes

Why it is worth supporting:

- very low operational overhead
- easy local reset and snapshotting
- reasonable to commit a DB snapshot to git when the goal is portability or reproducibility, not mergeable history
- good match for local graph and memory iteration

Constraints to accept:

- weaker concurrent write behavior
- fewer built-in operational controls for team sharing
- local file management and migration discipline still matter

### Postgres mode

Best fit:

- local developer environments that want parity with production or team workflows
- shared team deployments on a LAN, VPN, or cloud network
- cloud-hosted central graph and memory services with concurrent writers

Why it remains important:

- better multi-user concurrency
- clearer path for pooled connections, backups, access control, and managed hosting
- stronger default posture for shared durable memory and graph updates across a team

Modes to support explicitly:

- local Postgres for parity and migration testing
- shared self-hosted Postgres for small teams
- managed/cloud Postgres for central team memory and retrieval infrastructure

Architectural consequence:

- one retrieval and storage abstraction
- SQLite should be first-class for local single-dev mode, not only a benchmark convenience
- Postgres should be the default shared/team mode
- backend-specific features should stay optional behind capability checks

## Near-Term Next Steps

The next work should follow from the current benchmark and direction, not from feature sprawl.

### 1. Align the live Postgres embedding schema with the app default

Why:

- the live DB is still on `vector(24)` while the app default is `1024`
- we can validate the live path today by overriding `ARIADNE_EMBEDDING_DIMENSIONS=24`, but that should not remain the normal workflow

Focus:

- either migrate the embeddings table to `1024` or intentionally pin local dev to `24`
- document the reset/migration path clearly
- keep `ariadne doctor` as the quick compatibility check

### 2. Expose Ariadne retrieval and memory over MCP, then dogfood it in Codex

Why:

- this is the fastest path to proving Ariadne is useful in real coding-agent workflows
- dogfooding through Codex will expose missing retrieval tools, poor ergonomics, and bad defaults quickly
- MemPalace reinforces that agent-side usability matters as much as storage internals

Focus:

- expose `search`, `retrieve`, `pack-context`, `graph`, `trace`, and memory CRUD over MCP
- make retrieval traces easy for the agent to inspect
- add a simple Codex-facing workflow for storing and retrieving task memory
- dogfood the Ariadne MCP tools in this repo before broader integration

### 3. Add conversation and session ingest for durable memory

Why:

- Ariadne is strong on code retrieval but still thin on conversation memory capture
- this is the clearest area where MemPalace has useful product ideas

Focus:

- add a `memory ingest-convos` path for chat exports and session transcripts
- add a `memory ingest-threads` path for archived thread markdown files such as `*_thread_summary.md`
- index archived thread summaries as files on disk and optionally derive imported candidate memories from them
- store raw transcripts plus derived candidate memories
- keep source metadata such as archive path, thread identifier, and capture time on imported memories
- require review before durable persistence for weakly inferred links
- add pre-compaction or save-hook capture points where practical

### 4. Improve doc and config ranking where candidates already exist

Why:

- Spinner and Quay both now show that most remaining doc/config misses are `scored_too_low`, not absent
- this means the next gains are in support-artifact ordering and preservation, not broad graph expansion

Focus:

- doc ranking
- config ranking
- support artifact preservation
- file promotion that does not crowd out docs and config
- close the remaining `README.md` and config misses that still show up as `not_generated`

### 5. Close the remaining symbol-generation gaps

Why:

- a smaller but still important set of symbols are still `not_generated`

Focus:

- better symbol alias/query rewriting
- module-name expansion
- improve summaries for constants, returned keys, and helper functions
- target the concrete misses now showing up in diagnostics:
  - Spinner: `build_plan`, `load_openai_settings`, `record_session_run`
  - Quay: `append_audit_event`

### 6. Keep Spinner and Quay as a shared scoreboard for retrieval changes

Why:

- Spinner alone is no longer enough
- Quay gives us a second repo shape with config-heavy and service-oriented retrieval pressure
- the latest ranking pass improved both, which is the behavior we want to preserve

Next:

- compare Spinner and Quay side-by-side after each retrieval change
- avoid improving one while silently regressing the other
- treat cross-fixture improvement as the default success criterion for ranking work

### 7. Keep live traces and retrieval logs central to tuning work

Why:

- the live path is now inspectable, and it exposed slightly different failure patterns than the SQLite benchmark harness
- we should not do blind ranking work again now that we can look at real stage counts and packed outputs

Next:

- use `ariadne trace` and `ariadne retrieval-logs` for weak queries before changing ranking
- compare live and benchmark misses for the same task
- keep the packed-context output reviewable when tuning ranking

### 8. Add release and migration hygiene

Why:

- the live Postgres mismatch already showed that schema and embedding migrations can drift
- agent infrastructure should survive packaging and environment mistakes

Next:

- document DB reset vs migration paths clearly
- add packaging/release checklist items
- consider failing fast when configured dimensions and DB vector type differ

### 9. Add a second-order trust layer

Why:

- good retrieval is necessary, but operator trust is what makes this usable in real coding workflows

Next:

- reviewed memory links
- reviewed doc/code links where confidence is weak
- explicit user-facing provenance in packed context

## Ranking Notes

The latest ranking pass was worthwhile.

What improved:

- Spinner improved from `0.708` to `0.72` avg artifact recall
- Quay improved from `0.557` to `0.692` avg artifact recall
- both fixture repos now have `1.0` file hit rate
- both fixture repos now have `1.0` memory hit rate
- both fixture repos now have `1.0` symbol hit rate
- Spinner now has `1.0` test hit rate
- Quay doc hit rate improved from `0.667` to `0.833`

What changed:

- rerank support files based on query and mode intent
- promote symbols from already-ranked files using query aliases
- allow a slightly larger symbol set into packed context

What this means:

- candidate generation is much healthier than before
- remaining work is mostly in support-artifact ordering and a narrow set of symbol-generation gaps
- we should be more careful now about overfitting one fixture, because the retrieval system is starting to look broadly functional

Immediate next moves:

- prototype Ariadne MCP tools and use them from Codex
- design a conversation/session ingest format and review loop
- design a thread-summary import path that supports both on-disk indexing and MCP-driven memory capture
- improve README and top-level docs retrieval for `understand` queries
- tighten config-file recall for support-heavy queries
- close the remaining symbol misses: `build_plan`, `load_openai_settings`, `record_session_run`, `append_audit_event`
- add adaptive graph-weight features before making large graph-schema expansions
- keep vector compression as a later optimization track, not a current blocker
- prefer targeted fixes confirmed by both benchmark and live traces, and revert changes that do not clear the shared scoreboard
- review the `agentic-memory` collection and turn the highest-signal references into explicit Ariadne design notes

## Adaptive Edge Weighting

The next ranking step should probably include learned edge weights rather than treating every traversable edge of a given type as equally useful.

Working idea:

- track how often an edge is traversed during retrieval
- track how often traversed edges lead to artifacts that survive reranking and packing
- track stronger positive signals such as benchmark success, explicit user selection, or reviewed memory acceptance
- track negative signals such as frequent traversal that still ends in `packed_out`, `scored_too_low`, or obvious irrelevance

This is reinforcement-like, but the first version should stay simple:

- start with per-edge and per-edge-type weights derived from counts and decay
- use those weights as ranking features, not as automatic graph mutations
- keep weights scoped by repo, and possibly by user or workspace later
- decay old behavior so one past task does not dominate future retrieval forever

Good initial candidates:

- `DOC_DESCRIBES_SYMBOL`
- `DOC_DESCRIBES_FILE`
- `CONFIG_AFFECTS_FILE`
- explicit memory-to-code links
- commit-to-file edges once commit nodes exist

Guardrails:

- reviewed edges should start with a stronger prior than fully automatic edges
- traversal frequency alone should not imply truth; popular but noisy edges must be suppressible
- benchmark and trace instrumentation should stay the source of truth for whether weighting actually helps

## Done

The following items from the backlog are now at least MVP-implemented:

- `TEST_COVERS_SYMBOL`
- `DOC_DESCRIBES_SYMBOL`
- `DOC_DESCRIBES_FILE`
- `CONFIG_AFFECTS_FILE`
- explicit memory-to-code linking support
- type-aware context packing
- retrieval benchmark runner
- retrieval miss diagnostics (`not_generated`, `scored_too_low`, `packed_out`)
- lexical ranking improvements for files, symbols, and memories
- persisted retrieval-log diagnostics
- `ariadne trace`
- `ariadne retrieval-logs`
- `ariadne doctor`
- `ARIADNE_STRICT_DB_COMPATIBILITY`
- live fixture benchmark runner against the real Postgres-backed path

These are implemented, but not all are fully tuned yet.

## Commit Nodes

Add commits as first-class nodes in the graph instead of only storing snapshot SHAs on repos and files.

Why:

- improve historical retrieval
- support "why did this change?" workflows
- attach memories and decisions to concrete code changes
- prepare for blame, PR, incident, and architecture history features

Minimum useful schema:

- `commits` table
- fields:
  - `id`
  - `repo_id`
  - `sha`
  - `parent_shas`
  - `author_name`
  - `author_email`
  - `authored_at`
  - `committed_at`
  - `subject`
  - `body`

Useful graph edges:

- `COMMIT_TOUCHED_FILE`
- `COMMIT_MODIFIED_SYMBOL` later
- `MEMORY_RELATES_TO_COMMIT`
- `COMMIT_ON_BRANCH` later

Suggested rollout:

1. Add commit schema and migration.
2. Ingest current commit metadata during repo registration and indexing.
3. Add commit-to-file edges for changed files.
4. Extend retrieval with commit-aware history and memory linking.

## Human-in-the-Loop Linking

Add a human review step when connecting non-code-tree nodes to code-tree nodes.

Examples:

- documentation to files or symbols
- ADRs or design notes to subsystems
- incidents to affected code paths
- similar but separate code trees that should be linked by convention, architecture, or historical context

Why:

- these links are high-value but easier to get wrong than direct code structure
- incorrect durable links will pollute retrieval and memory expansion
- human confirmation is especially useful before persisting long-lived graph edges

Good candidates for reviewed linking:

- `DOC_DESCRIBES_SYMBOL`
- `APPLIES_TO`
- `RELATES_TO`
- `CONSTRAINS`
- `WARNS_ABOUT`
- cross-repo or cross-subsystem similarity links

Possible workflow:

1. Generate candidate links automatically from lexical and semantic signals.
2. Present candidates with short evidence snippets.
3. Require explicit human confirm/reject before durable persistence.
4. Store reviewer decision and confidence.

Potential extension:

- represent cross-tree or loosely related code groups as memories, conventions, or design notes when the relationship is architectural rather than strictly structural
- attach those reviewed memory nodes to both code trees instead of forcing a direct code-to-code edge

## Graph Backlog

The current graph is much healthier than it was initially, but it is still not deep enough for Ariadne's full goals. The benchmark results now suggest that the next graph work should be more selective and should focus on edges that close real benchmark gaps instead of adding breadth for its own sake.

### Priority 1

#### `TEST_COVERS_SYMBOL`

Status: implemented in MVP form.

Why:

- current benchmark test hit rate is weak
- test expansion should be graph-driven, not just lexical

Initial extraction ideas:

- infer from imports in test files
- infer from `test_<symbol>` naming
- infer from same-module test file conventions

#### `DOC_DESCRIBES_SYMBOL`

Status: implemented in MVP form.

Why:

- docs are mostly retrieved lexically today
- architecture notes and ADRs should attach to real code nodes

Initial extraction ideas:

- lexical candidate generation
- semantic candidate generation
- optional human confirmation before durable persistence

#### `CONFIG_AFFECTS_FILE`

Status: implemented in MVP form.

Why:

- config relevance is currently too implicit
- many coding tasks need to know which configuration shapes runtime behavior

Initial extraction ideas:

- imported config modules
- explicit config key references
- path and subsystem conventions

#### Explicit memory-to-code edges

Status: supported, but still needs better reviewed-link workflows and stronger ranking behavior.

Why:

- memory retrieval should not depend only on text overlap
- durable historical context is more useful when attached to the exact file, symbol, or subsystem

Initial edge types:

- `APPLIES_TO`
- `RELATES_TO`
- `CONSTRAINS`
- `WARNS_ABOUT`

### Priority 2

#### Ranking and generation follow-up from Spinner diagnostics

Why:

- the benchmark has moved from "can Ariadne find things at all?" to "does Ariadne rank the right things high enough?"
- the largest remaining miss bucket is now `scored_too_low`
- a smaller but still meaningful miss bucket remains for symbols that are never generated

Immediate next steps:

- improve doc/config ranking without giving back file/test recall
- improve symbol generation for query forms like:
  - `build plan` -> `build_plan`
  - `record session run` -> `record_session_run`
  - `load openai settings` -> `load_openai_settings`
- add lightweight alias/query rewriting for underscored symbols and module names
- separate support-artifact preservation from general top-k competition more cleanly

#### `SYMBOL_CALLS_SYMBOL`

Why:

- improves refactor and bugfix graph expansion
- especially helpful for caller/callee queries

Initial extraction ideas:

- conservative AST-based extraction for Python
- only link when the callee resolves locally with high confidence

#### `SYMBOL_REFERENCES_SYMBOL`

Why:

- captures important non-call relationships
- useful for constants, shared helpers, provider names, and strategy objects

#### Subsystem nodes

Why:

- many decisions and conventions apply to a subsystem, not a single file
- subsystem-level retrieval is cleaner than attaching the same memory to many files

Possible edges:

- `FILE_BELONGS_TO_SUBSYSTEM`
- `SYMBOL_BELONGS_TO_SUBSYSTEM`
- memory `APPLIES_TO` subsystem

#### Second fixture repo

Why:

- Spinner is useful, but we should not overfit the system to one fixture shape
- a second repo should stress a different structure:
  - heavier config usage
  - more docs and runbooks
  - different naming patterns
  - different graph topology

Goal:

- use a second benchmark fixture before treating Spinner scores as broadly meaningful

### Priority 3

#### Commit nodes and commit edges

Why:

- enables historical retrieval
- supports commit-aware architecture and incident context

Likely edges:

- `COMMIT_TOUCHED_FILE`
- `MEMORY_RELATES_TO_COMMIT`
- `COMMIT_ON_BRANCH`

#### Reviewed cross-tree similarity links

Why:

- some important relationships are architectural rather than structural
- these should likely be reviewed before becoming durable graph edges

Possible representations:

- direct reviewed cross-tree edges
- memory/convention nodes attached to both sides

### Suggested implementation order

Completed:

1. `TEST_COVERS_SYMBOL`
2. `DOC_DESCRIBES_SYMBOL`
3. `DOC_DESCRIBES_FILE`
4. `CONFIG_AFFECTS_FILE`
5. explicit memory-to-code links

Next:

1. ranking and symbol-generation follow-up from Spinner diagnostics
2. adaptive edge weighting from retrieval traces and benchmark outcomes
3. `SYMBOL_CALLS_SYMBOL`
4. subsystem nodes
5. second fixture repo
6. commit nodes
7. reviewed cross-tree similarity links
