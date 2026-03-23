from __future__ import annotations

import argparse

from spinner.agent.runtime import AgentRuntime
from spinner.models import TaskMode, TaskRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spinner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run-task")
    run.add_argument("workspace")
    run.add_argument("query")
    run.add_argument("--mode", default="understand", choices=[mode.value for mode in TaskMode])
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    runtime = AgentRuntime()

    if args.command == "run-task":
        request = TaskRequest(
            task_id="task-001",
            query=args.query,
            mode=TaskMode(args.mode),
            workspace=args.workspace,
        )
        result = runtime.run(request)
        print(f"{result.status}: {result.message}")


if __name__ == "__main__":
    main()
