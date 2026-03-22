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
