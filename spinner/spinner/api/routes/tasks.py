from __future__ import annotations

from dataclasses import asdict

from spinner.agent.runtime import AgentRuntime
from spinner.models import TaskMode, TaskRequest


def run_task_payload(workspace: str, query: str, mode: str = "understand") -> dict:
    runtime = AgentRuntime()
    result = runtime.run(
        TaskRequest(
            task_id="api-task",
            query=query,
            mode=TaskMode(mode),
            workspace=workspace,
        )
    )
    return asdict(result)
