from __future__ import annotations

from spinner.models import PatchPlan


def validate_patch_plan(plan: PatchPlan) -> list[str]:
    warnings: list[str] = []
    if len(plan.target_files) > 3:
        warnings.append("Patch plan touches many files.")
    if not plan.rollback_hint:
        warnings.append("Patch plan missing rollback hint.")
    return warnings
