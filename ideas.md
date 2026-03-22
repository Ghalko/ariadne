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
