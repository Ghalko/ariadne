# ContextBench Smoke Result - 2026-05-07

This is the first real public ContextBench run against Ariadne.

## Setup

- Dataset: `Contextbench/ContextBench`
- Config: `contextbench_verified`
- Export path used locally: `/tmp/contextbench_sample.jsonl`
- Rows exported: 2
- Evaluated rows: 1
- Repo: `astropy/astropy`
- Local checkout: `/tmp/contextbench_repos/astropy`
- Base commit: `6500928dc0e57be8f06d1162eacc3ba5e2eff692`
- Ariadne DB: temporary SQLite DB
- Retrieval limit: 8
- `include_code`: false

Commands:

```bash
env UV_CACHE_DIR=/tmp/uv-cache /Users/ghalko/.local/bin/uv run python benchmarks/fetch_contextbench_sample.py \
  --output /tmp/contextbench_sample.jsonl \
  --length 2

git clone --filter=blob:none https://github.com/astropy/astropy.git /tmp/contextbench_repos/astropy
git -C /tmp/contextbench_repos/astropy checkout 6500928dc0e57be8f06d1162eacc3ba5e2eff692

env UV_CACHE_DIR=/tmp/uv-cache /Users/ghalko/.local/bin/uv run python benchmarks/run_contextbench.py \
  --input /tmp/contextbench_sample.jsonl \
  --repo-map astropy/astropy=/tmp/contextbench_repos/astropy \
  --max-instances 1 \
  --json
```

## Result

- Instance: `SWE-Bench-Verified__python__maintenance__bugfix__deb49033`
- Gold files: 9
- Retrieved files: 8
- Hit files: 0
- File recall: `0.0`
- File precision: `0.0`
- Packed token estimate: `922`
- Gold-context token estimate: `3572`
- Recall per 1k packed tokens: `0.0`

Retrieved files:

- `astropy/coordinates/transformations.py`
- `astropy/coordinates/angle_utilities.py`
- `astropy/io/fits/tests/test_header.py`
- `astropy/io/fits/tests/test_checksum.py`
- `github/PULL_REQUEST_TEMPLATE.md`
- `astropy/io/fits/tests/test_diff.py`
- `astropy/coordinates/tests/test_icrs_observed_transformations.py`
- `docs/conftest.py`

Gold files:

- `astropy/coordinates/attributes.py`
- `astropy/coordinates/builtin_frames/__init__.py`
- `astropy/coordinates/builtin_frames/altaz.py`
- `astropy/coordinates/builtin_frames/cirs_observed_transforms.py`
- `astropy/coordinates/builtin_frames/hadec.py`
- `astropy/coordinates/builtin_frames/intermediate_rotation_transforms.py`
- `astropy/coordinates/builtin_frames/itrs.py`
- `astropy/coordinates/builtin_frames/utils.py`
- `astropy/coordinates/matrix_utilities.py`

## Interpretation

Ariadne produced compact output on this instance, but it did not retrieve the gold context. The useful signal is:

- token count alone is not enough
- ContextBench immediately exposes retrieval quality gaps that Spinner and Quay did not
- the first failure pattern is not absence of related code in the repo; it is ranking and query interpretation on long issue statements

The run also exposed a benchmark-scale SQLite failure before scoring: long issue statements created too many lexical `OR` terms. That is fixed by capping lexical query terms and filtering common stopwords.

## Next Work

- Add a baseline retriever to `run_contextbench.py` so Ariadne can be compared against simple lexical/path retrieval on the same rows.
- Persist per-instance diagnostics from Ariadne retrieval in ContextBench output.
- Improve long issue query rewriting and domain term extraction before tuning ranking.
- Run at least 5 verified rows after adding diagnostics and baselines.
