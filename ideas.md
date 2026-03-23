# Ideas

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

The current graph is still too shallow for Ariadne's goals. The benchmark results especially suggest that test, doc, config, and memory relationships need to become explicit graph edges rather than remaining heuristic retrieval behavior.

### Priority 1

#### `TEST_COVERS_SYMBOL`

Why:

- current benchmark test hit rate is weak
- test expansion should be graph-driven, not just lexical

Initial extraction ideas:

- infer from imports in test files
- infer from `test_<symbol>` naming
- infer from same-module test file conventions

#### `DOC_DESCRIBES_SYMBOL`

Why:

- docs are mostly retrieved lexically today
- architecture notes and ADRs should attach to real code nodes

Initial extraction ideas:

- lexical candidate generation
- semantic candidate generation
- optional human confirmation before durable persistence

#### `CONFIG_AFFECTS_FILE`

Why:

- config relevance is currently too implicit
- many coding tasks need to know which configuration shapes runtime behavior

Initial extraction ideas:

- imported config modules
- explicit config key references
- path and subsystem conventions

#### Explicit memory-to-code edges

Why:

- memory retrieval should not depend only on text overlap
- durable historical context is more useful when attached to the exact file, symbol, or subsystem

Initial edge types:

- `APPLIES_TO`
- `RELATES_TO`
- `CONSTRAINS`
- `WARNS_ABOUT`

### Priority 2

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

1. `TEST_COVERS_SYMBOL`
2. `DOC_DESCRIBES_SYMBOL`
3. `CONFIG_AFFECTS_FILE`
4. explicit memory-to-code links
5. `SYMBOL_CALLS_SYMBOL`
6. subsystem nodes
7. commit nodes
8. reviewed cross-tree similarity links
