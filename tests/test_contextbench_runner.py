from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

RUNNER_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "run_contextbench.py"
SPEC = importlib.util.spec_from_file_location("run_contextbench", RUNNER_PATH)
assert SPEC is not None
run_contextbench = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["run_contextbench"] = run_contextbench
SPEC.loader.exec_module(run_contextbench)

estimate_tokens = run_contextbench.estimate_tokens
load_rows = run_contextbench.load_rows
parse_gold_context = run_contextbench.parse_gold_context
score_context = run_contextbench.score_context
baseline_retrieve = run_contextbench.baseline_retrieve

FETCHER_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "fetch_contextbench_sample.py"
FETCHER_SPEC = importlib.util.spec_from_file_location("fetch_contextbench_sample", FETCHER_PATH)
assert FETCHER_SPEC is not None
fetch_contextbench_sample = importlib.util.module_from_spec(FETCHER_SPEC)
assert FETCHER_SPEC.loader is not None
sys.modules["fetch_contextbench_sample"] = fetch_contextbench_sample
FETCHER_SPEC.loader.exec_module(fetch_contextbench_sample)


def test_parse_gold_context_from_contextbench_json_string() -> None:
    spans = parse_gold_context(
        json.dumps(
            [
                {
                    "file": "./pkg/service.py",
                    "start_line": 10,
                    "end_line": 20,
                    "content": "def run():\n    return True\n",
                }
            ]
        )
    )

    assert spans[0].file == "pkg/service.py"
    assert spans[0].start_line == 10
    assert spans[0].end_line == 20


def test_score_context_reports_file_precision_recall_tokens_and_span_overlap() -> None:
    gold_spans = parse_gold_context(
        [
            {"file": "pkg/service.py", "start_line": 10, "end_line": 20, "content": "important code"},
            {"file": "pkg/config.py", "start_line": 1, "end_line": 3, "content": "settings"},
        ]
    )
    context = {
        "files": [{"path": "pkg/service.py"}, {"path": "pkg/extra.py"}],
        "symbols": [],
        "memories": [],
        "snippets": [{"file": "pkg/service.py", "lines": [15, 18], "code": "return True"}],
    }
    baseline_context = {
        "files": [{"path": "pkg/config.py"}],
        "symbols": [],
        "memories": [],
        "snippets": [],
    }
    diagnostics = {
        "stages": {
            "lexical": {"files": [{"path": "pkg/config.py"}]},
            "selected": {"files": [{"path": "pkg/config.py"}]},
            "packed": {"files": [{"path": "pkg/service.py"}]},
        },
        "stage_counts": {"packed": {"files": 1, "symbols": 0, "memories": 0}},
    }

    result = score_context(
        instance_id="task-1",
        repo="owner/repo",
        base_commit="abc123",
        gold_spans=gold_spans,
        context=context,
        baseline_context=baseline_context,
        diagnostics=diagnostics,
    )

    assert result.file_recall == 0.5
    assert result.file_precision == 0.5
    assert result.snippet_span_recall == 0.5
    assert result.hit_files == ["pkg/service.py"]
    assert result.missing_files == ["pkg/config.py"]
    assert result.packed_token_estimate == estimate_tokens(json.dumps(context, sort_keys=True))
    assert result.recall_per_1k_tokens > 0
    assert result.baseline_file_recall == 0.5
    assert result.baseline_file_precision == 1.0
    assert result.baseline_hit_files == ["pkg/config.py"]
    assert result.missing_file_diagnostics == {"pkg/config.py": "packed_out"}
    assert result.stage_counts == {"packed": {"files": 1, "symbols": 0, "memories": 0}}


def test_baseline_retrieve_scores_path_and_content_overlap(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pkg").mkdir()
    (repo / "pkg" / "sliced_wcs.py").write_text("class SlicedLowLevelWCS:\n    pass\n", encoding="utf-8")
    (repo / "pkg" / "unrelated.py").write_text("nothing useful\n", encoding="utf-8")

    context = baseline_retrieve(query="SlicedLowLevelWCS world_to_pixel", repo_path=repo, limit=1)

    assert [item["path"] for item in context["files"]] == ["pkg/sliced_wcs.py"]


def test_load_rows_supports_jsonl(tmp_path) -> None:
    path = tmp_path / "contextbench.jsonl"
    path.write_text('{"instance_id": "one"}\n{"instance_id": "two"}\n', encoding="utf-8")

    assert [row["instance_id"] for row in load_rows(path)] == ["one", "two"]


def test_fetcher_builds_contextbench_rows_api_url(monkeypatch) -> None:
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"rows": [{"row": {"instance_id": "sample"}}]}'

    def fake_urlopen(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(fetch_contextbench_sample, "urlopen", fake_urlopen)

    rows = fetch_contextbench_sample.fetch_rows(config="contextbench_verified", split="train", offset=2, length=3)

    assert rows == [{"instance_id": "sample"}]
    assert "dataset=Contextbench%2FContextBench" in captured["url"]
    assert "config=contextbench_verified" in captured["url"]
    assert "split=train" in captured["url"]
    assert "offset=2" in captured["url"]
    assert "length=3" in captured["url"]
    assert captured["timeout"] == 60
