from __future__ import annotations

from spinner.models import ContextBundle, RunResult, TaskRequest

RUN_LOG: list[dict] = []


def record_session_run(*, request: TaskRequest, result: RunResult, context: ContextBundle) -> None:
    RUN_LOG.append(
        {
            "task_id": request.task_id,
            "workspace": request.workspace,
            "mode": request.mode.value,
            "query": request.query,
            "status": result.status,
            "changed_files": result.changed_files,
            "estimated_tokens": context.estimated_tokens,
        }
    )
