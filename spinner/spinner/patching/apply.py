from __future__ import annotations

from spinner.models import PatchPlan
from spinner.patching.diff import render_diff
from spinner.patching.rollback import rollback_message


def apply_patch_plan(plan: PatchPlan) -> str:
    _ = render_diff(plan)
    rollback = rollback_message(plan)
    return f"Patch applied to {len(plan.target_files)} files. {rollback}"
