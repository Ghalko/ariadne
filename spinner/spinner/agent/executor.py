from __future__ import annotations

from spinner.models import PatchPlan, RunResult
from spinner.patching.apply import apply_patch_plan
from spinner.patching.validation import validate_patch_plan


def execute_plan(plan: PatchPlan) -> RunResult:
    warnings = validate_patch_plan(plan)
    status = "applied"
    message = apply_patch_plan(plan)
    if warnings:
        status = "applied_with_warnings"
    return RunResult(
        task_id=plan.task_id,
        status=status,
        message=message,
        changed_files=plan.target_files,
        warnings=warnings,
    )
