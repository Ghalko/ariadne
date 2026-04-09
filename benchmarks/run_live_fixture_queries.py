from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from ariadne_index.bootstrap import build_services
from ariadne_index.db import session_scope
from ariadne_index.schemas import MemoryCreate, MemoryLinkCreate, RepoCreate
from run_spinner_benchmarks import (
    BENCHMARK_ROOT,
    PROJECT_ROOT,
    evaluate_query,
    render_report,
    seed_doc_memories,
    summarize,
)


SPINNER_QUERIES = BENCHMARK_ROOT / "queries.json"
QUAY_QUERIES = BENCHMARK_ROOT / "quay_queries.json"
SPINNER_ROOT = PROJECT_ROOT / "spinner"
QUAY_ROOT = PROJECT_ROOT / "quay"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Ariadne retrieval benchmarks against live indexed fixture repos.")
    parser.add_argument(
        "--fixtures",
        nargs="+",
        default=["spinner", "quay"],
        choices=["spinner", "quay"],
        help="Fixture repos to evaluate.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument("--limit", type=int, default=None, help="Optional global limit override.")
    parser.add_argument("--database-url", default=None, help="Override database URL.")
    parser.add_argument(
        "--seed-memories",
        action="store_true",
        default=True,
        help="Seed fixture docs as durable memories before evaluation.",
    )
    parser.add_argument(
        "--no-seed-memories",
        dest="seed_memories",
        action="store_false",
        help="Skip fixture memory seeding.",
    )
    parser.add_argument(
        "--bootstrap-missing",
        action="store_true",
        default=False,
        help="Register and index missing fixture repos in the live DB before evaluation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_live_queries(
        fixtures=args.fixtures,
        database_url=args.database_url,
        limit_override=args.limit,
        seed_memories=args.seed_memories,
        bootstrap_missing=args.bootstrap_missing,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
        return

    blocks = [_render_live_report(report) for report in payload["reports"]]
    print("\n\n".join(blocks))


def run_live_queries(
    *,
    fixtures: list[str],
    database_url: str | None = None,
    limit_override: int | None = None,
    seed_memories: bool = True,
    bootstrap_missing: bool = False,
) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    with session_scope(database_url) as session:
        services = build_services(session)
        for fixture in fixtures:
            report = _run_fixture(
                fixture,
                services=services,
                limit_override=limit_override,
                seed_memories=seed_memories,
                bootstrap_missing=bootstrap_missing,
            )
            reports.append(report)
    return {"reports": reports}


def _run_fixture(
    fixture: str,
    *,
    services: dict,
    limit_override: int | None,
    seed_memories: bool,
    bootstrap_missing: bool,
) -> dict[str, Any]:
    fixture_root, queries_path, repo_name, report_title = _fixture_config(fixture)
    try:
        repo = services["repos"].get_repo_by_name(repo_name)
    except ValueError:
        if not bootstrap_missing:
            return {
                "report_title": f"{report_title} live",
                "repo_name": repo_name,
                "summary": {"queries": 0, "error": f"Unknown repo: {repo_name}. Re-run with --bootstrap-missing."},
                "results": [],
            }
        repo = services["repos"].add_repo(RepoCreate(name=repo_name, local_path=str(fixture_root)))
        services["indexing"].index_repo(repo)

    if seed_memories:
        seed_doc_memories(
            repo.id,
            services["memory"],
            services["memory"].session,
            fixture_root=fixture_root,
            MemoryCreate=MemoryCreate,
            MemoryLinkCreate=MemoryLinkCreate,
        )

    queries = json.loads(queries_path.read_text())
    results = [
        evaluate_query(
            query=query,
            retrieval=services["retrieval"],
            repo=repo,
            limit_override=limit_override,
        )
        for query in queries
    ]
    return {
        "report_title": f"{report_title} live",
        "repo_name": repo_name,
        "summary": summarize(results, total_queries=len(queries)),
        "results": [asdict(result) for result in results],
    }


def _fixture_config(fixture: str) -> tuple[Path, Path, str, str]:
    if fixture == "spinner":
        return SPINNER_ROOT, SPINNER_QUERIES, "spinner", "Spinner"
    return QUAY_ROOT, QUAY_QUERIES, "quay", "Quay"


def _render_live_report(report: dict[str, Any]) -> str:
    if "error" in report["summary"]:
        return f"{report['report_title']}\nerror: {report['summary']['error']}"
    return render_report(report)


if __name__ == "__main__":
    main()
