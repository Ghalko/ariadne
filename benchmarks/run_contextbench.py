from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class GoldSpan:
    file: str
    start_line: int | None = None
    end_line: int | None = None
    content: str = ""


@dataclass(slots=True)
class ContextBenchResult:
    instance_id: str
    repo: str
    base_commit: str
    skipped_reason: str | None
    gold_files: list[str]
    retrieved_files: list[str]
    hit_files: list[str]
    missing_files: list[str]
    file_recall: float
    file_precision: float
    snippet_span_recall: float | None
    packed_token_estimate: int
    gold_context_token_estimate: int
    recall_per_1k_tokens: float
    baseline_retrieved_files: list[str]
    baseline_hit_files: list[str]
    baseline_file_recall: float
    baseline_file_precision: float
    baseline_token_estimate: int
    baseline_recall_per_1k_tokens: float
    missing_file_diagnostics: dict[str, str]
    stage_counts: dict[str, dict[str, int]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Ariadne retrieval on exported ContextBench rows.")
    parser.add_argument("--input", required=True, help="ContextBench export path: .jsonl, .json, .csv, or .parquet.")
    parser.add_argument(
        "--repo-map",
        action="append",
        default=[],
        metavar="REPO=PATH",
        help="Map a ContextBench repo value such as astropy/astropy to a local checkout.",
    )
    parser.add_argument(
        "--repo-base-dir",
        default=None,
        help="Directory containing checkouts named by repo basename or owner__repo.",
    )
    parser.add_argument("--database-url", default=None, help="Database URL. Defaults to a temporary SQLite DB.")
    parser.add_argument("--max-instances", type=int, default=None, help="Limit evaluated rows.")
    parser.add_argument("--repo-filter", action="append", default=[], help="Only evaluate matching repo values.")
    parser.add_argument("--source-filter", action="append", default=[], help="Only evaluate matching source values.")
    parser.add_argument("--limit", type=int, default=8, help="Ariadne retrieval limit.")
    parser.add_argument("--include-code", action="store_true", help="Include Ariadne snippets and score span overlap.")
    parser.add_argument(
        "--allow-commit-mismatch",
        action="store_true",
        help="Evaluate even when local checkout HEAD does not match ContextBench base_commit.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_contextbench(
        input_path=Path(args.input),
        repo_map=parse_repo_map(args.repo_map),
        repo_base_dir=Path(args.repo_base_dir) if args.repo_base_dir else None,
        database_url=args.database_url,
        max_instances=args.max_instances,
        repo_filter=set(args.repo_filter),
        source_filter=set(args.source_filter),
        limit=args.limit,
        include_code=args.include_code,
        allow_commit_mismatch=args.allow_commit_mismatch,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(render_report(payload))


def run_contextbench(
    *,
    input_path: Path,
    repo_map: dict[str, Path],
    repo_base_dir: Path | None,
    database_url: str | None,
    max_instances: int | None,
    repo_filter: set[str],
    source_filter: set[str],
    limit: int,
    include_code: bool,
    allow_commit_mismatch: bool,
) -> dict[str, Any]:
    os.environ["ARIADNE_EMBEDDING_PROVIDER"] = "deterministic"
    os.environ.pop("OPENAI_API_KEY", None)

    from ariadne_index.bootstrap import build_services
    from ariadne_index.config import get_settings
    from ariadne_index.db import init_database, session_scope
    from ariadne_index.schemas import RepoCreate

    get_settings.cache_clear()
    rows = [
        row
        for row in load_rows(input_path)
        if (not repo_filter or str(row.get("repo")) in repo_filter)
        and (not source_filter or str(row.get("source")) in source_filter)
    ]
    if max_instances is not None:
        rows = rows[:max_instances]

    with tempfile.TemporaryDirectory(prefix="ariadne-contextbench-") as temp_dir:
        db_url = database_url or f"sqlite+pysqlite:///{Path(temp_dir) / 'contextbench.db'}"
        if database_url is None:
            init_database(db_url)
        with session_scope(db_url) as session:
            services = build_services(session)
            results = [
                evaluate_row(
                    row,
                    services=services,
                    RepoCreate=RepoCreate,
                    repo_map=repo_map,
                    repo_base_dir=repo_base_dir,
                    limit=limit,
                    include_code=include_code,
                    allow_commit_mismatch=allow_commit_mismatch,
                )
                for row in rows
            ]

    return {"summary": summarize(results), "results": [asdict(result) for result in results]}


def evaluate_row(
    row: dict[str, Any],
    *,
    services: dict[str, Any],
    RepoCreate,
    repo_map: dict[str, Path],
    repo_base_dir: Path | None,
    limit: int,
    include_code: bool,
    allow_commit_mismatch: bool,
) -> ContextBenchResult:
    instance_id = str(row.get("instance_id") or row.get("original_inst_id") or "")
    repo_slug = str(row.get("repo") or "")
    base_commit = str(row.get("base_commit") or "")
    gold_spans = parse_gold_context(row.get("gold_context"))
    empty = score_context(
        instance_id=instance_id,
        repo=repo_slug,
        base_commit=base_commit,
        gold_spans=gold_spans,
        context={"files": [], "symbols": [], "memories": [], "snippets": []},
        baseline_context={"files": [], "symbols": [], "memories": [], "snippets": []},
        diagnostics={},
    )

    repo_path = resolve_repo_path(repo_slug, repo_map=repo_map, repo_base_dir=repo_base_dir)
    if repo_path is None:
        empty.skipped_reason = "repo_not_mapped"
        return empty
    if not repo_path.exists():
        empty.skipped_reason = "repo_path_missing"
        return empty

    current_commit = git_commit(repo_path)
    if base_commit and current_commit and current_commit != base_commit and not allow_commit_mismatch:
        empty.skipped_reason = f"commit_mismatch:{current_commit}"
        return empty

    repo_name = f"contextbench:{repo_slug.replace('/', '__')}:{(base_commit or current_commit or 'unknown')[:12]}"
    try:
        repo = services["repos"].get_repo_by_name(repo_name)
    except ValueError:
        repo = services["repos"].add_repo(RepoCreate(name=repo_name, local_path=str(repo_path)))
        services["indexing"].index_repo(repo)

    payload = services["retrieval"].retrieve(
        query=str(row.get("problem_statement") or ""),
        mode="bugfix",
        repo=repo,
        limit=limit,
        include_code=include_code,
    )
    baseline_context = baseline_retrieve(
        query=str(row.get("problem_statement") or ""),
        repo_path=repo_path,
        limit=limit,
    )
    return score_context(
        instance_id=instance_id,
        repo=repo_slug,
        base_commit=base_commit,
        gold_spans=gold_spans,
        context=payload["context"],
        baseline_context=baseline_context,
        diagnostics=payload.get("diagnostics", {}),
    )


def score_context(
    *,
    instance_id: str,
    repo: str,
    base_commit: str,
    gold_spans: list[GoldSpan],
    context: dict[str, Any],
    baseline_context: dict[str, Any],
    diagnostics: dict[str, Any],
) -> ContextBenchResult:
    gold_files = sorted({span.file for span in gold_spans})
    retrieved_files = [normalize_path(item["path"]) for item in context.get("files", []) if item.get("path")]
    hit_files = [path for path in gold_files if path in set(retrieved_files)]
    missing_files = [path for path in gold_files if path not in set(retrieved_files)]
    file_recall = safe_div(len(hit_files), len(gold_files), empty=1.0)
    file_precision = safe_div(len(hit_files), len(retrieved_files), empty=1.0 if not gold_files else 0.0)
    packed_token_estimate = estimate_tokens(json.dumps(context, sort_keys=True))
    gold_context_token_estimate = estimate_tokens("\n".join(span.content for span in gold_spans))
    recall_per_1k_tokens = safe_div(file_recall, packed_token_estimate / 1000, empty=0.0)
    snippet_span_recall = score_snippet_span_recall(gold_spans, context.get("snippets", []))
    baseline_files = [normalize_path(item["path"]) for item in baseline_context.get("files", []) if item.get("path")]
    baseline_hit_files = [path for path in gold_files if path in set(baseline_files)]
    baseline_file_recall = safe_div(len(baseline_hit_files), len(gold_files), empty=1.0)
    baseline_file_precision = safe_div(len(baseline_hit_files), len(baseline_files), empty=1.0 if not gold_files else 0.0)
    baseline_token_estimate = estimate_tokens(json.dumps(baseline_context, sort_keys=True))
    baseline_recall_per_1k_tokens = safe_div(baseline_file_recall, baseline_token_estimate / 1000, empty=0.0)
    stage_values = diagnostic_stage_values(diagnostics)

    return ContextBenchResult(
        instance_id=instance_id,
        repo=repo,
        base_commit=base_commit,
        skipped_reason=None,
        gold_files=gold_files,
        retrieved_files=retrieved_files,
        hit_files=hit_files,
        missing_files=missing_files,
        file_recall=round(file_recall, 4),
        file_precision=round(file_precision, 4),
        snippet_span_recall=snippet_span_recall,
        packed_token_estimate=packed_token_estimate,
        gold_context_token_estimate=gold_context_token_estimate,
        recall_per_1k_tokens=round(recall_per_1k_tokens, 4),
        baseline_retrieved_files=baseline_files,
        baseline_hit_files=baseline_hit_files,
        baseline_file_recall=round(baseline_file_recall, 4),
        baseline_file_precision=round(baseline_file_precision, 4),
        baseline_token_estimate=baseline_token_estimate,
        baseline_recall_per_1k_tokens=round(baseline_recall_per_1k_tokens, 4),
        missing_file_diagnostics=classify_missing_files(gold_files, stage_values),
        stage_counts=diagnostics.get("stage_counts", {}),
    )


def baseline_retrieve(*, query: str, repo_path: Path, limit: int) -> dict[str, Any]:
    terms = query_terms(query)
    candidates: list[tuple[int, str, str]] = []
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file() or should_skip_path(path, repo_path):
            continue
        relative = path.relative_to(repo_path).as_posix()
        content = path.read_text(encoding="utf-8", errors="ignore")
        score = baseline_score(relative, content, terms)
        if score <= 0:
            continue
        candidates.append((score, relative, content))

    candidates.sort(key=lambda item: (item[0], -len(item[1])), reverse=True)
    return {
        "files": [
            {
                "path": relative,
                "summary": first_nonempty_line(content)[:300],
            }
            for _, relative, content in candidates[:limit]
        ],
        "symbols": [],
        "memories": [],
        "snippets": [],
    }


def baseline_score(relative_path: str, content: str, terms: list[str]) -> int:
    haystack_path = relative_path.lower()
    haystack_text = content[:8000].lower()
    basename = haystack_path.rsplit("/", 1)[-1]
    score = 0
    for term in terms:
        if term in basename:
            score += 8
        if term in haystack_path:
            score += 5
        if term in haystack_text:
            score += 1
    return score


def should_skip_path(path: Path, root: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    parts = set(relative.split("/"))
    if parts.intersection({".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", "build", "dist"}):
        return True
    return path.suffix.lower() not in {".py", ".md", ".rst", ".toml", ".yaml", ".yml", ".json", ".cfg", ".ini"}


def first_nonempty_line(content: str) -> str:
    return next((line.strip() for line in content.splitlines() if line.strip()), "")


def query_terms(query: str) -> list[str]:
    stopwords = {
        "about",
        "after",
        "also",
        "and",
        "are",
        "because",
        "been",
        "before",
        "but",
        "can",
        "could",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "into",
        "not",
        "our",
        "out",
        "same",
        "should",
        "than",
        "that",
        "the",
        "then",
        "there",
        "these",
        "this",
        "when",
        "where",
        "which",
        "while",
        "with",
        "would",
        "you",
    }
    seen: set[str] = set()
    terms: list[str] = []
    for term in re_split(query):
        lowered = term.lower()
        if len(lowered) < 3 or lowered in stopwords or lowered in seen:
            continue
        seen.add(lowered)
        terms.append(lowered)
    return terms[:80]


def diagnostic_stage_values(diagnostics: dict[str, Any]) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    for stage, stage_payload in (diagnostics.get("stages") or {}).items():
        values[stage] = {normalize_path(item["path"]) for item in stage_payload.get("files", []) if item.get("path")}
    return values


def classify_missing_files(gold_files: list[str], stages: dict[str, set[str]]) -> dict[str, str]:
    selected = stages.get("selected", set())
    packed = stages.get("packed", set())
    generated = set().union(
        stages.get("lexical", set()),
        stages.get("support", set()),
        stages.get("graph", set()),
        stages.get("semantic", set()),
    )
    diagnostics: dict[str, str] = {}
    for path in gold_files:
        if path in packed:
            continue
        if path in selected:
            diagnostics[path] = "packed_out"
        elif path in generated:
            diagnostics[path] = "scored_too_low"
        else:
            diagnostics[path] = "not_generated"
    return diagnostics


def score_snippet_span_recall(gold_spans: list[GoldSpan], snippets: list[dict[str, Any]]) -> float | None:
    gold_with_lines = [span for span in gold_spans if span.start_line is not None and span.end_line is not None]
    if not gold_with_lines or not snippets:
        return None

    hit_count = 0
    for span in gold_with_lines:
        for snippet in snippets:
            if normalize_path(str(snippet.get("file", ""))) != span.file:
                continue
            lines = snippet.get("lines") or []
            if len(lines) != 2:
                continue
            if ranges_overlap(span.start_line or 0, span.end_line or 0, int(lines[0]), int(lines[1])):
                hit_count += 1
                break
    return round(hit_count / len(gold_with_lines), 4)


def parse_gold_context(value: Any) -> list[GoldSpan]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        raise ValueError("gold_context must be a JSON list")

    spans: list[GoldSpan] = []
    for item in value:
        if not isinstance(item, dict) or not item.get("file"):
            continue
        spans.append(
            GoldSpan(
                file=normalize_path(str(item["file"])),
                start_line=optional_int(item.get("start_line")),
                end_line=optional_int(item.get("end_line")),
                content=str(item.get("content") or ""),
            )
        )
    return spans


def load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload["data"]
        raise ValueError("JSON input must be a list or an object with a data list")
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".parquet":
        try:
            import pandas as pd  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("parquet input requires pandas and a parquet engine") from exc
        return pd.read_parquet(path).to_dict(orient="records")
    raise ValueError(f"unsupported input format: {path.suffix}")


def parse_repo_map(values: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"repo map must be REPO=PATH: {value}")
        repo, path = value.split("=", 1)
        mapping[repo] = Path(path)
    return mapping


def resolve_repo_path(repo: str, *, repo_map: dict[str, Path], repo_base_dir: Path | None) -> Path | None:
    if repo in repo_map:
        return repo_map[repo]
    if repo_base_dir is None or not repo:
        return None
    owner_repo = repo.replace("/", "__")
    basename = repo.rsplit("/", 1)[-1]
    for candidate in (repo_base_dir / owner_repo, repo_base_dir / basename):
        if candidate.exists():
            return candidate
    return None


def git_commit(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def summarize(results: list[ContextBenchResult]) -> dict[str, Any]:
    evaluated = [result for result in results if result.skipped_reason is None]
    skipped: dict[str, int] = {}
    for result in results:
        if result.skipped_reason:
            reason = result.skipped_reason.split(":", 1)[0]
            skipped[reason] = skipped.get(reason, 0) + 1

    return {
        "instances": len(results),
        "evaluated": len(evaluated),
        "skipped": skipped,
        "avg_file_recall": average([result.file_recall for result in evaluated]),
        "avg_file_precision": average([result.file_precision for result in evaluated]),
        "avg_snippet_span_recall": average(
            [result.snippet_span_recall for result in evaluated if result.snippet_span_recall is not None]
        ),
        "avg_packed_token_estimate": average([result.packed_token_estimate for result in evaluated]),
        "avg_gold_context_token_estimate": average([result.gold_context_token_estimate for result in evaluated]),
        "avg_recall_per_1k_tokens": average([result.recall_per_1k_tokens for result in evaluated]),
        "avg_baseline_file_recall": average([result.baseline_file_recall for result in evaluated]),
        "avg_baseline_file_precision": average([result.baseline_file_precision for result in evaluated]),
        "avg_baseline_token_estimate": average([result.baseline_token_estimate for result in evaluated]),
        "avg_baseline_recall_per_1k_tokens": average(
            [result.baseline_recall_per_1k_tokens for result in evaluated]
        ),
        "missing_file_reasons": aggregate_missing_reasons(evaluated),
    }


def render_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "ContextBench Ariadne retrieval results",
        f"instances: {summary['instances']}",
        f"evaluated: {summary['evaluated']}",
        f"skipped: {summary['skipped']}",
        f"avg file recall: {summary['avg_file_recall']}",
        f"avg file precision: {summary['avg_file_precision']}",
        f"avg snippet span recall: {summary['avg_snippet_span_recall']}",
        f"avg packed token estimate: {summary['avg_packed_token_estimate']}",
        f"avg gold context token estimate: {summary['avg_gold_context_token_estimate']}",
        f"avg recall per 1k tokens: {summary['avg_recall_per_1k_tokens']}",
        f"avg baseline file recall: {summary['avg_baseline_file_recall']}",
        f"avg baseline file precision: {summary['avg_baseline_file_precision']}",
        f"avg baseline token estimate: {summary['avg_baseline_token_estimate']}",
        f"avg baseline recall per 1k tokens: {summary['avg_baseline_recall_per_1k_tokens']}",
        f"missing files: {summary['missing_file_reasons']}",
        "",
        "Per-instance snapshot:",
    ]
    for result in payload["results"]:
        if result["skipped_reason"]:
            lines.append(f"- {result['instance_id']}: skipped={result['skipped_reason']}")
            continue
        lines.append(
            f"- {result['instance_id']}: recall={result['file_recall']} precision={result['file_precision']} "
            f"tokens={result['packed_token_estimate']} baseline_recall={result['baseline_file_recall']} "
            f"baseline_tokens={result['baseline_token_estimate']} hits={result['hit_files']}"
        )
    return "\n".join(lines)


def aggregate_missing_reasons(results: list[ContextBenchResult]) -> dict[str, int]:
    counts = {"not_generated": 0, "scored_too_low": 0, "packed_out": 0}
    for result in results:
        for reason in result.missing_file_diagnostics.values():
            counts[reason] += 1
    return counts


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return math.ceil(len(text) / 4)


def normalize_path(path: str) -> str:
    return path.strip().lstrip("./")


def re_split(text: str) -> list[str]:
    import re

    return re.split(r"[_\W]+", text)


def optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def ranges_overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    return max(left_start, right_start) <= min(left_end, right_end)


def safe_div(numerator: float, denominator: float, *, empty: float) -> float:
    if denominator == 0:
        return empty
    return numerator / denominator


def average(values: list[float | int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


if __name__ == "__main__":
    main()
