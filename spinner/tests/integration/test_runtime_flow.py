from __future__ import annotations

from spinner.agent.runtime import AgentRuntime
from spinner.models import TaskMode, TaskRequest
from spinner.sessions.history import list_runs


def test_runtime_records_session_run() -> None:
    runtime = AgentRuntime()
    result = runtime.run(
        TaskRequest(
            task_id="runtime-001",
            query="Refactor provider fallback and include rollback notes",
            mode=TaskMode.refactor,
            workspace="spinner",
        )
    )

    assert result.status in {"applied", "applied_with_warnings"}
    assert list_runs()
