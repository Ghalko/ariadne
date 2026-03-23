# Benchmarks

This folder contains labeled benchmark data for Ariadne.

## Layout

- `queries.json`: labeled retrieval tasks
- `run_spinner_benchmarks.py`: benchmark runner for the local `spinner` fixture repo

## Run

From the Ariadne repo root:

```bash
PYTHONPATH=src .venv/bin/python benchmarks/run_spinner_benchmarks.py
```

JSON output:

```bash
PYTHONPATH=src .venv/bin/python benchmarks/run_spinner_benchmarks.py --json
```

## Notes

- paths in `gold_files`, `gold_tests`, and `gold_docs` are relative to the fixture repo root
- `gold_memories` may refer to future explicit memory nodes or to source documents that should become memories later
- the first benchmark target is the local `spinner/` fixture repo
