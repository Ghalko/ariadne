from __future__ import annotations

from spinner.agent.tasks import classify_task
from spinner.models import PatchPlan, TaskRequest


def build_plan(request: TaskRequest, candidate_paths: list[str]) -> PatchPlan:
    classification = classify_task(request)
    return PatchPlan(
        task_id=request.task_id,
        target_files=candidate_paths[:3],
        summary=f"{classification} task for query: {request.query}",
        rollback_hint="Use stored session snapshot before patch apply.",
    )
