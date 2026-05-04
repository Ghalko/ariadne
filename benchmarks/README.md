# Benchmarks

This folder contains labeled benchmark data for Ariadne.

## Layout

- `queries.json`: labeled retrieval tasks for `spinner`
- `quay_queries.json`: labeled retrieval tasks for `quay`
- `run_spinner_benchmarks.py`: benchmark runner for the local `spinner` fixture repo
- `run_quay_benchmarks.py`: benchmark runner for the local `quay` fixture repo
- `run_live_fixture_queries.py`: benchmark runner against live indexed fixture repos in the configured DB
- `run_contextbench.py`: adapter for exported ContextBench rows and local checked-out repos

## Run

From the Ariadne repo root:

```bash
PYTHONPATH=src .venv/bin/python benchmarks/run_spinner_benchmarks.py
```

JSON output:

```bash
PYTHONPATH=src .venv/bin/python benchmarks/run_spinner_benchmarks.py --json
```

Quay:

```bash
PYTHONPATH=src .venv/bin/python benchmarks/run_quay_benchmarks.py
```

Live DB-backed run:

```bash
PYTHONPATH=src .venv/bin/python benchmarks/run_live_fixture_queries.py --fixtures spinner quay
```

If the live DB is still on the older `vector(24)` schema, run with:

```bash
ARIADNE_EMBEDDING_DIMENSIONS=24 PYTHONPATH=src .venv/bin/python benchmarks/run_live_fixture_queries.py --fixtures spinner quay --bootstrap-missing
```

ContextBench adapter:

```bash
PYTHONPATH=src .venv/bin/python benchmarks/run_contextbench.py \
  --input data/contextbench_verified.jsonl \
  --repo-map astropy/astropy=/path/to/astropy \
  --max-instances 10
```

The adapter expects ContextBench rows with `repo`, `base_commit`, `problem_statement`, and `gold_context`.
It scores Ariadne's packed context against gold files and spans using file recall, file precision,
packed token estimate, gold-context token estimate, and recall per 1k packed tokens. For `.parquet`
exports, install `pandas` and a parquet engine or convert the dataset to JSONL first.

## Notes

- paths in `gold_files`, `gold_tests`, and `gold_docs` are relative to the fixture repo root
- `gold_memories` may refer to future explicit memory nodes or to source documents that should become memories later
- the first benchmark target is the local `spinner/` fixture repo
- the second benchmark target is the local `quay/` fixture repo
- benchmark output now includes miss diagnostics so each expected artifact is classified as `not_generated`, `scored_too_low`, or `packed_out`
- the live runner is useful for comparing the real Postgres-backed path against the temp-DB harness before making ranking changes
- ContextBench is the first public benchmark adapter because it directly evaluates coding-agent context retrieval quality and efficiency
