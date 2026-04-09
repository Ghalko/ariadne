from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_spinner_benchmarks import PROJECT_ROOT, render_report, run_benchmarks


BENCHMARK_ROOT = Path(__file__).resolve().parent
QUERIES_PATH = BENCHMARK_ROOT / "quay_queries.json"
QUAY_ROOT = PROJECT_ROOT / "quay"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Ariadne retrieval benchmarks against Quay.")
    parser.add_argument("--queries", default=str(QUERIES_PATH), help="Path to benchmark queries JSON.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument("--limit", type=int, default=None, help="Optional global limit override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_benchmarks(
        Path(args.queries),
        fixture_root=QUAY_ROOT,
        repo_name="quay",
        report_title="Quay",
        limit_override=args.limit,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(render_report(payload))


if __name__ == "__main__":
    main()
