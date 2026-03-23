# Spinner

Spinner is a local coding runtime fixture repo used to benchmark Ariadne's indexing, retrieval, memory, and context packing.

## Main Concepts

- workspaces track local repositories and active branches
- indexing summarizes files and symbols into a searchable graph
- retrieval combines lexical, semantic, graph, and memory-like signals
- context packing builds compact task prompts
- agent runtime plans and executes coding tasks
- patching applies changes with validation and rollback support
- sessions and telemetry record outcomes and incident notes

## Layout

- `spinner/workspace/`: local repo registration and status
- `spinner/indexing/`: file discovery, summaries, and graph hints
- `spinner/retrieval/`: lexical, semantic, graph, and ranking stages
- `spinner/context/`: token budgeting and snippet selection
- `spinner/agent/`: planning and task execution
- `spinner/patching/`: diff generation, validation, apply, and rollback
- `spinner/providers/`: chat and embedding provider configuration
- `spinner/sessions/`: session history and replay
- `spinner/telemetry/`: events, logs, and incidents
- `docs/`: ADRs, runbooks, and architecture notes
- `config/`: simple TOML configs used by the runtime

## Run

```bash
uv venv --python 3.14
source .venv/bin/activate
uv sync
spinner run-task spinner "Refactor provider fallback and include rollback notes" --mode refactor
```

Without activating the virtualenv:

```bash
uv run --python 3.14 spinner run-task spinner "Refactor provider fallback and include rollback notes" --mode refactor
```
